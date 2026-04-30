"""DataInterface for optogenetic stimulation TTL data."""

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils import DeepDict, dict_deep_update, load_dict_from_file
from pynwb import NWBFile
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite


class OptogeneticsTTLInterface(BaseDataInterface):
    """DataInterface for reading optogenetic stimulation TTL CSVs and writing to NWB.

    The TTL CSVs have 3 columns (no header):
      1. ISO wall-clock timestamp — NOT used for timing (per Meletis lab: not accurate per sample)
      2. frame (0-indexed) — used to compute per-sample times via ``frame / frame_rate``
      3. Boolean TTL state (True = laser on)

    Session start time is parsed from the filename (``{prefix}_{YYYY-MM-DD}T{HH_MM_SS}.csv``),
    A uniform frame rate can be used (confirmed by the lab) default is 30.0 Hz.

    Stimulation episodes are extracted by grouping consecutive True samples separated by gaps > 1s.
    Two classes of burst are excluded from both the ``OptogeneticSeries`` power trace and the
    ``stimulation_episodes`` ``TimeIntervals`` (pending lab confirmation):
    1. The first TTL burst, interpreted as an FP-acquisition sync pulse.
    2. Any additional burst whose duration exceeds ``max_stim_duration_s`` (default 1.5 s,
       well above the documented 1 s stimulation pulse and well below the observed ~5–10 s
       warm-up/calibration bursts that appear at the start of some sessions).

    Uses ndx-optogenetics (OptogeneticExperimentMetadata) to store rich device and virus metadata
    extracted from Mantas et al. (2026), including the ChRmine virus, SNc injection coordinates,
    and optical fiber parameters.
    """

    keywords = ("optogenetics", "laser", "stimulation", "TTL")

    def __init__(self, file_path: str | Path, verbose: bool = True):
        """Initialize OptogeneticsTTLInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the TTL CSV file.
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
        self.file_path = Path(file_path)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        opto_metadata_path = Path(__file__).parent / "optogenetics_metadata.yaml"
        opto_metadata = load_dict_from_file(opto_metadata_path)
        metadata = dict_deep_update(metadata, opto_metadata)

        session_start_time = self._get_session_start_time()
        metadata["NWBFile"]["session_start_time"] = session_start_time

        return metadata

    def _get_session_start_time(self) -> datetime:
        """Parse session start time from the TTL filename.

        Per Meletis lab: The filename encodes the true session start time.
        Expected format: {prefix}_{YYYY-MM-DD}T{HH_MM_SS}.csv, e.g. oft_2024-03-01T10_16_32.csv.
        Falls back to first-row timestamp if the filename does not match.
        """
        match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2})$", self.file_path.stem)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%dT%H_%M_%S")
        # Fallback — should not be reached for well-formed filenames
        df = pd.read_csv(self.file_path, header=None, names=["timestamp", "sample", "ttl"])
        return pd.to_datetime(df["timestamp"].iloc[0]).to_pydatetime().replace(tzinfo=None)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        video_frame_rate_hz: float = 30.0,
        intensity_mw: float = 1.0,
        frequency_hz: float = 40.0,
        start_fp: int | None = None,
        max_stim_duration_s: float = 1.5,
    ) -> None:
        df = pd.read_csv(self.file_path, header=None, names=["timestamp", "frame", "ttl"])
        frame_indices = df["frame"].values.astype(np.float64)
        # Per Meletis lab: column 1 (absolute wall-clock timestamps) is not
        # accurate per sample. Use the 0-indexed frame counter (column 2) divided by the
        # confirmed uniform frame rate (30 Hz).
        time_seconds = frame_indices / video_frame_rate_hz
        ttl_values = df["ttl"].values.astype(bool)
        intensity_w = intensity_mw / 1000.0

        # Identify stimulation episodes (groups of True separated by > 1s gap)
        true_indices = np.where(ttl_values)[0]
        if len(true_indices) == 0:
            return

        # Validate details.csv `start.fp` against the TTL trace (sanity check for file mis-joins).
        # `start.fp` is the value of the TTL `sample` column at the first TTL True row (NOT the
        # row number — the `sample` column can have gaps from dropped frames).
        if start_fp is not None:
            first_true_sample = int(df["frame"].iloc[true_indices[0]])
            if first_true_sample != start_fp:
                raise ValueError(
                    f"details.csv start.fp={start_fp} does not match the TTL `sample` column "
                    f"at the first True row (got {first_true_sample}). This usually indicates "
                    f"a file mis-join between details.csv and the TTL CSV "
                    f"({self.file_path.name})."
                )

        # Compute burst boundaries in `true_indices` (consecutive True samples separated by
        # a gap > 1 s define a new burst). `burst_boundaries` holds the start position of each
        # burst within `true_indices`, with a sentinel at the end for uniform slicing.
        true_times = time_seconds[true_indices]
        gaps = np.diff(true_times)
        burst_boundaries = np.concatenate([[0], np.where(gaps > 1.0)[0] + 1, [len(true_indices)]])

        # --- Exclude non-stimulation bursts
        # Two rules, both conservative:
        # (1) the first burst is the FP-acquisition sync pulse (timing coincides with FP-start
        #     at ~8.1 s; details.csv.start.fp equals the TTL `sample` value at the first True
        #     row);
        # (2) any burst longer than `max_stim_duration_s` (default 1.5 s) is a warm-up /
        #     calibration pulse. The documented protocol is 1 s stim bursts; observed
        #     warm-up bursts are ~5-10 s, so there is a wide safe gap.
        stim_burst_starts_in_true: list[int] = []
        excluded_burst_indices: list[np.ndarray] = []
        for burst_idx in range(len(burst_boundaries) - 1):
            b_start = burst_boundaries[burst_idx]
            b_end = burst_boundaries[burst_idx + 1]
            duration = true_times[b_end - 1] - true_times[b_start]
            is_first_burst = burst_idx == 0
            is_overlong = duration > max_stim_duration_s
            if is_first_burst or is_overlong:
                excluded_burst_indices.append(true_indices[b_start:b_end])
            else:
                stim_burst_starts_in_true.append(int(b_start))

        # Build OptogeneticSeries power trace with excluded-burst samples zeroed out.
        power_data = np.where(ttl_values, intensity_w, 0.0).astype(np.float64)
        if excluded_burst_indices:
            power_data[np.concatenate(excluded_burst_indices)] = 0.0

        opto_meta = (metadata or {}).get("Optogenetics", {})
        site_meta = opto_meta.get("OptogeneticStimulusSite", {})
        excitation_lambda = float(site_meta.get("excitation_lambda", 640.0))
        fmt_kwargs = dict(
            intensity_mw=intensity_mw,
            intensity_w=intensity_w,
            frequency_hz=frequency_hz,
            excitation_lambda=excitation_lambda,
        )

        # --- ndx-optogenetics: rich device and virus metadata ---
        self._add_optogenetics_metadata(
            nwbfile=nwbfile,
            metadata=metadata,
            intensity_mw=intensity_mw,
            frequency_hz=frequency_hz,
        )

        # --- Core NWB: OptogeneticSeries (continuous TTL power trace) ---
        site_name = site_meta.get("name")
        ogen_site = nwbfile.ogen_sites.get(site_name)
        series_meta = opto_meta.get("OptogeneticSeries", {})
        ogen_series = OptogeneticSeries(
            name=series_meta.get("name"),
            description=(series_meta.get("description") or "").format(**fmt_kwargs),
            data=power_data,
            timestamps=time_seconds,
            site=ogen_site,
        )
        nwbfile.add_stimulus(ogen_series)

        # --- Stimulation episodes as TimeIntervals (onset/offset per real stim burst) ---
        stim_meta = opto_meta.get("StimulationEpisodes", {})
        stim_intervals = nwbfile.create_time_intervals(
            name=stim_meta.get("name"),
            description=(stim_meta.get("description") or "").format(**fmt_kwargs),
        )

        # Emit one TimeIntervals row per real stimulation burst (excluded bursts already filtered).
        # `stim_burst_starts_in_true` holds each kept burst's start position within `true_indices`;
        # look up the matching end position from `burst_boundaries` (same index in the full list).
        starts_set = set(stim_burst_starts_in_true)
        for burst_idx in range(len(burst_boundaries) - 1):
            b_start = int(burst_boundaries[burst_idx])
            if b_start not in starts_set:
                continue
            b_end = int(burst_boundaries[burst_idx + 1])
            episode_onset = true_times[b_start]
            episode_offset = true_times[b_end - 1]
            stim_intervals.add_row(start_time=episode_onset, stop_time=episode_offset)

    def _add_optogenetics_metadata(
        self, nwbfile: NWBFile, metadata: dict | None, intensity_mw: float, frequency_hz: float
    ) -> None:
        """Add ndx-optogenetics metadata (devices, virus, injection sites) to the NWBFile.

        All structural metadata (coordinates, manufacturers, model numbers, virus info) is read
        from the ``Optogenetics`` section of the metadata dict, which is populated from
        metadata.yaml via the standard neuroconv deep-merge flow in convert_session.py.
        Session-specific values (intensity_mw, frequency_hz) are passed directly.
        """
        from ndx_ophys_devices import Effector, FiberInsertion, ViralVector, ViralVectorInjection
        from ndx_optogenetics import (
            ExcitationSource,
            ExcitationSourceModel,
            OpticalFiber,
            OpticalFiberModel,
            OptogeneticEffectors,
            OptogeneticExperimentMetadata,
            OptogeneticSitesTable,
            OptogeneticViruses,
            OptogeneticVirusInjections,
        )

        opto_meta = (metadata or {}).get("Optogenetics", {})

        # Read excitation_lambda early so it can be used in model creation
        site_meta = opto_meta.get("OptogeneticStimulusSite", {})
        excitation_lambda = float(site_meta.get("excitation_lambda", 640.0))

        # Common format kwargs for description templates (session-specific values)
        fmt_kwargs = dict(intensity_mw=intensity_mw, frequency_hz=frequency_hz, excitation_lambda=excitation_lambda)

        # --- ExcitationSourceModel: manufacturer/specs for the laser type ---
        # wavelength_range_in_nm is computed from excitation_lambda rather than read from YAML
        # to avoid dict_deep_update deduplicating [640, 640] → [640].
        esm_meta = opto_meta.get("ExcitationSourceModel", {})
        laser_model = ExcitationSourceModel(
            name=esm_meta.get("name"),
            manufacturer=esm_meta.get("manufacturer"),
            source_type=esm_meta.get("source_type"),
            excitation_mode=esm_meta.get("excitation_mode"),
            wavelength_range_in_nm=[excitation_lambda, excitation_lambda],
        )
        nwbfile.add_device_model(laser_model)

        # --- ExcitationSource: the specific laser instance, linked to its model ---
        es_meta = opto_meta.get("ExcitationSource") or {}
        laser = ExcitationSource(
            name=es_meta.get("name"),
            description=(es_meta.get("description") or "").format(**fmt_kwargs),
            model=laser_model,
            power_in_W=intensity_mw / 1000.0,
        )
        nwbfile.add_device(laser)

        # --- OpticalFiberModel: specs shared by both implanted fibers ---
        ofm_meta = opto_meta.get("OpticalFiberModel", {})
        fiber_model = OpticalFiberModel(
            name=ofm_meta.get("name"),
            manufacturer=ofm_meta.get("manufacturer"),
            model_number=ofm_meta.get("model_number"),
            numerical_aperture=float(ofm_meta.get("numerical_aperture")),
            core_diameter_in_um=float(ofm_meta.get("core_diameter_in_um")),
            ferrule_name=ofm_meta.get("ferrule_name"),
        )
        nwbfile.add_device_model(fiber_model)

        # --- OpticalFiber instances: one per hemisphere, each linked to the shared model ---
        fiber_objects = {}
        for fiber_spec in opto_meta.get("OpticalFibers", []):
            fiber_insertion = FiberInsertion(
                name="fiber_insertion",
                insertion_position_ap_in_mm=fiber_spec["insertion_position_ap_in_mm"],
                insertion_position_ml_in_mm=fiber_spec["insertion_position_ml_in_mm"],
                insertion_position_dv_in_mm=fiber_spec["insertion_position_dv_in_mm"],
                position_reference=fiber_spec.get("position_reference"),
                hemisphere=fiber_spec["hemisphere"],
            )
            fiber = OpticalFiber(
                name=fiber_spec["name"],
                fiber_insertion=fiber_insertion,
                description=fiber_spec.get("description") or "",
                model=fiber_model,
            )
            nwbfile.add_device(fiber)
            fiber_objects[fiber_spec["name"]] = fiber

        # --- OptogeneticStimulusSite (required by OptogeneticSeries) ---
        ogen_site = OptogeneticStimulusSite(
            name=site_meta.get("name"),
            description=(site_meta.get("description") or "").format(**fmt_kwargs),
            device=laser,
            excitation_lambda=excitation_lambda,
            location=site_meta.get("location"),
        )
        nwbfile.add_ogen_site(ogen_site)

        # --- Viral vector ---
        vv_meta = opto_meta.get("ViralVector", {})
        virus = ViralVector(
            name=vv_meta.get("name"),
            construct_name=vv_meta.get("construct_name"),
            manufacturer=vv_meta.get("manufacturer"),
            titer_in_vg_per_ml=float(vv_meta.get("titer_in_vg_per_ml")),
            description=vv_meta.get("description") or "",
        )

        # --- Virus injections (bilateral) ---
        injection_objects = {}
        for inj_spec in opto_meta.get("VirusInjections", []):
            inj_desc = (inj_spec.get("description") or "").format(
                volume_nL=inj_spec["volume_in_uL"] * 1000,
                construct_name=vv_meta.get("construct_name"),
            )
            inj = ViralVectorInjection(
                name=inj_spec["name"],
                location=inj_spec["location"],
                hemisphere=inj_spec["hemisphere"],
                reference=inj_spec.get("reference"),
                ap_in_mm=inj_spec["ap_in_mm"],
                ml_in_mm=inj_spec["ml_in_mm"],
                dv_in_mm=inj_spec["dv_in_mm"],
                volume_in_uL=inj_spec["volume_in_uL"],
                viral_vector=virus,
                description=inj_desc,
            )
            injection_objects[inj_spec["name"]] = inj

        # Map effector hemisphere → injection name
        _hemisphere_to_injection = {
            inj_spec["hemisphere"]: inj_spec["name"] for inj_spec in opto_meta.get("VirusInjections", [])
        }

        # --- Effectors (ChRmine, one per hemisphere) ---
        effector_objects = []
        for eff_spec in opto_meta.get("Effectors", []):
            hemisphere = eff_spec.get("hemisphere") or ("left" if eff_spec["name"].endswith("_left") else "right")
            inj_name = _hemisphere_to_injection.get(hemisphere)
            inj_obj = injection_objects.get(inj_name)
            eff_desc = (eff_spec.get("description") or "").format(**fmt_kwargs)
            effector = Effector(
                name=eff_spec["name"],
                label=eff_spec.get("label"),
                description=eff_desc,
                manufacturer=eff_spec.get("manufacturer"),
                viral_vector_injection=inj_obj,
            )
            effector_objects.append(effector)

        # --- OptogeneticSitesTable: one row per hemisphere ---
        # Map fiber name suffix to effector
        fiber_name_to_effector = {eff.name.replace("ChRmine_", "optical_fiber_snc_"): eff for eff in effector_objects}

        sites_table_meta = opto_meta.get("OptogeneticSitesTable", {})
        sites_table = OptogeneticSitesTable(
            description=(sites_table_meta.get("description") or "").format(**fmt_kwargs)
        )
        for col in sites_table_meta.get("columns", []):
            sites_table.add_column(name=col["name"], description=col["description"])

        for fiber_name, fiber_obj in fiber_objects.items():
            effector = fiber_name_to_effector.get(fiber_name)
            sites_table.add_row(data={"effector": effector, "excitation_source": laser, "optical_fiber": fiber_obj})

        # --- OptogeneticExperimentMetadata: top-level metadata container ---
        all_injections = list(injection_objects.values())
        opto_experiment_meta = OptogeneticExperimentMetadata(
            stimulation_software=opto_meta.get("stimulation_software"),
            optogenetic_sites_table=sites_table,
            optogenetic_effectors=OptogeneticEffectors(effectors=effector_objects),
            optogenetic_viruses=OptogeneticViruses(viral_vectors=[virus]),
            optogenetic_virus_injections=OptogeneticVirusInjections(viral_vector_injections=all_injections),
        )
        nwbfile.add_lab_meta_data(opto_experiment_meta)
