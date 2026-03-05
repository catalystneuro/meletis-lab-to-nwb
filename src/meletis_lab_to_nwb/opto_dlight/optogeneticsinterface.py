"""DataInterface for optogenetic stimulation TTL data."""

from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils import DeepDict, dict_deep_update, load_dict_from_file
from pynwb import NWBFile
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite


class OptogeneticsTTLInterface(BaseDataInterface):
    """DataInterface for reading optogenetic stimulation TTL CSVs and writing to NWB.

    The TTL CSVs have 3 columns (no header): ISO timestamp, sample index, and boolean (True/False)
    indicating whether the laser was on at each ~143 Hz sample. The first burst of True values
    corresponds to fiber photometry system activation and is excluded from the optogenetic data.

    Stimulation episodes are extracted by grouping consecutive True samples separated by gaps > 1s.
    Each episode represents a nosepoke-triggered bilateral SNc laser stimulation (40 Hz, 1s on / 3s off).

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
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        intensity_mw: float = 1.0,
        frequency_hz: float = 40.0,
    ) -> None:
        df = pd.read_csv(self.file_path, header=None, names=["timestamp", "sample", "ttl"])
        timestamps = pd.to_datetime(df["timestamp"])
        session_start = timestamps.iloc[0]

        # Convert to seconds relative to session start
        time_seconds = (timestamps - session_start).dt.total_seconds().values
        ttl_values = df["ttl"].values.astype(bool)

        # Build the OptogeneticSeries: power in watts when laser is on, 0 when off
        intensity_w = intensity_mw / 1000.0
        power_data = np.where(ttl_values, intensity_w, 0.0).astype(np.float64)

        # Identify stimulation episodes (groups of True separated by > 1s gap)
        true_indices = np.where(ttl_values)[0]
        if len(true_indices) == 0:
            return

        true_times = time_seconds[true_indices]
        gaps = np.diff(true_times)
        burst_boundaries = np.where(gaps > 1.0)[0] + 1
        burst_starts = np.concatenate([[0], burst_boundaries])

        # Skip the first burst (fiber photometry system activation)
        if len(burst_starts) > 1:
            first_stim_idx = true_indices[burst_starts[1]]
        else:
            return

        rate = 1.0 / np.median(np.diff(time_seconds[:1000]))

        # Trim data: start 1s before the first real stimulation episode
        buffer_samples = int(rate)  # 1s of samples at the actual TTL sampling rate (~143 Hz)
        trim_start = max(0, first_stim_idx - buffer_samples)

        if stub_test:
            # For stub test, only keep first 300 samples after trim
            trim_end = min(trim_start + 300, len(time_seconds))
        else:
            trim_end = len(time_seconds)

        trimmed_time = time_seconds[trim_start:trim_end]
        trimmed_power = power_data[trim_start:trim_end]

        # Shift timestamps so the series starts at the trimmed time
        starting_time = trimmed_time[0]

        # --- ndx-optogenetics: rich device and virus metadata ---
        self._add_optogenetics_metadata(
            nwbfile=nwbfile,
            metadata=metadata,
            intensity_mw=intensity_mw,
            frequency_hz=frequency_hz,
        )

        # --- Core NWB: OptogeneticSeries (continuous TTL power trace) ---
        ogen_site = nwbfile.ogen_sites.get("OptogeneticStimulusSite")
        ogen_series = OptogeneticSeries(
            name="OptogeneticSeries",
            description=(
                f"Optogenetic stimulation TTL trace. Values represent laser power in watts "
                f"({intensity_mw} mW = {intensity_w:.4f} W when on, 0 when off). "
                f"Protocol: {frequency_hz} Hz pulse train, 1 s stimulation triggered by nosepoke, "
                f"3 s inter-stimulation interval. Bilateral SNc ChRmine activation. "
                f"The first TTL burst (fiber photometry system activation) has been excluded."
            ),
            data=trimmed_power,
            rate=rate,
            starting_time=starting_time,
            site=ogen_site,
        )
        nwbfile.add_stimulus(ogen_series)

        # --- Stimulation episodes as TimeIntervals (onset/offset per nosepoke-triggered burst) ---
        stim_intervals = nwbfile.create_time_intervals(
            name="stimulation_episodes",
            description=(
                "Nosepoke-triggered optogenetic stimulation episodes. Each row represents one "
                "stimulation burst (1 s of 40 Hz ChRmine laser in bilateral SNc). "
                "The first TTL burst (fiber photometry system activation) is excluded. "
                f"Session laser intensity: {intensity_mw} mW, wavelength: 640 nm."
            ),
        )

        # Extract episode onset/offset times (skip first burst)
        for burst_idx in range(1, len(burst_starts)):
            b_start = burst_starts[burst_idx]
            b_end = burst_starts[burst_idx + 1] if burst_idx + 1 < len(burst_starts) else len(true_indices)
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
            name=esm_meta.get("name", "cobalt_640nm_laser_model"),
            manufacturer=esm_meta.get("manufacturer", "Cobalt"),
            source_type=esm_meta.get("source_type", "Solid-State Laser"),
            excitation_mode=esm_meta.get("excitation_mode", "one-photon"),
            wavelength_range_in_nm=[excitation_lambda, excitation_lambda],
        )
        nwbfile.add_device_model(laser_model)

        # --- ExcitationSource: the specific laser instance, linked to its model ---
        es_meta = opto_meta.get("ExcitationSource") or {}
        laser = ExcitationSource(
            name="laser",
            description=es_meta.get("description", "").format(**fmt_kwargs),
            model=laser_model,
            power_in_W=intensity_mw / 1000.0,
        )
        nwbfile.add_device(laser)

        # --- OpticalFiberModel: specs shared by both implanted fibers ---
        ofm_meta = opto_meta.get("OpticalFiberModel", {})
        fiber_model = OpticalFiberModel(
            name=ofm_meta.get("name", "RWD_R-FOC-BL200C-22NA_model"),
            manufacturer=ofm_meta.get("manufacturer", "RWD"),
            model_number=ofm_meta.get("model_number", "R-FOC-BL200C-22NA"),
            numerical_aperture=float(ofm_meta.get("numerical_aperture", 0.22)),
            core_diameter_in_um=float(ofm_meta.get("core_diameter_in_um", 200.0)),
            ferrule_name=ofm_meta.get("ferrule_name", "ceramic ferrule"),
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
                position_reference=fiber_spec.get("position_reference", "bregma at the cortical surface"),
                hemisphere=fiber_spec["hemisphere"],
            )
            fiber = OpticalFiber(
                name=fiber_spec["name"],
                fiber_insertion=fiber_insertion,
                description=fiber_spec.get("description", "Optical fiber for SNc optogenetic stimulation."),
                model=fiber_model,
            )
            nwbfile.add_device(fiber)
            fiber_objects[fiber_spec["name"]] = fiber

        # --- OptogeneticStimulusSite (required by OptogeneticSeries) ---
        site_location = site_meta.get("location", "substantia nigra pars compacta (SNc), bilateral")
        ogen_site = OptogeneticStimulusSite(
            name="OptogeneticStimulusSite",
            description=site_meta.get("description", "").format(**fmt_kwargs),
            device=laser,
            excitation_lambda=excitation_lambda,
            location=site_location,
        )
        nwbfile.add_ogen_site(ogen_site)

        # --- Viral vector ---
        vv_meta = opto_meta.get("ViralVector", {})
        virus = ViralVector(
            name=vv_meta.get("name", "chrmine_virus"),
            construct_name=vv_meta.get("construct_name", "AAV8-nEF-Coff/Fon-ChRmine-oScarlet"),
            manufacturer=vv_meta.get("manufacturer", "Addgene"),
            titer_in_vg_per_ml=float(vv_meta.get("titer_in_vg_per_ml", 1e13)),
            description=vv_meta.get("description", ""),
        )

        # --- Virus injections (bilateral) ---
        injection_objects = {}
        for inj_spec in opto_meta.get("VirusInjections", []):
            inj_desc = inj_spec.get("description", "").format(
                volume_nL=inj_spec["volume_in_uL"] * 1000,
                construct_name=vv_meta.get("construct_name", "AAV8-nEF-Coff/Fon-ChRmine-oScarlet"),
            )
            inj = ViralVectorInjection(
                name=inj_spec["name"],
                location=inj_spec["location"],
                hemisphere=inj_spec["hemisphere"],
                reference=inj_spec.get("reference", "bregma at the cortical surface"),
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
            eff_desc = eff_spec.get("description", "").format(**fmt_kwargs)
            effector = Effector(
                name=eff_spec["name"],
                label=eff_spec.get("label", "ChRmine"),
                description=eff_desc,
                manufacturer=eff_spec.get("manufacturer", "Addgene"),
                viral_vector_injection=inj_obj,
            )
            effector_objects.append(effector)

        # --- OptogeneticSitesTable: one row per hemisphere ---
        # Map fiber name suffix to effector
        fiber_name_to_effector = {eff.name.replace("ChRmine_", "optical_fiber_"): eff for eff in effector_objects}

        sites_table_meta = opto_meta.get("OptogeneticSitesTable", {})
        sites_table = OptogeneticSitesTable(description=sites_table_meta.get("description", "").format(**fmt_kwargs))
        sites_table.add_column(name="excitation_source", description="Laser used for optogenetic stimulation.")
        sites_table.add_column(name="optical_fiber", description="Implanted optical fiber.")

        for fiber_name, fiber_obj in fiber_objects.items():
            effector = fiber_name_to_effector.get(fiber_name)
            sites_table.add_row(data={"effector": effector, "excitation_source": laser, "optical_fiber": fiber_obj})

        # --- OptogeneticExperimentMetadata: top-level metadata container ---
        all_injections = list(injection_objects.values())
        opto_experiment_meta = OptogeneticExperimentMetadata(
            stimulation_software=opto_meta.get(
                "stimulation_software", "Bonsai v2.6.3 (Lopes et al., 2015) + custom Arduino IDE script"
            ),
            optogenetic_sites_table=sites_table,
            optogenetic_effectors=OptogeneticEffectors(effectors=effector_objects),
            optogenetic_viruses=OptogeneticViruses(viral_vectors=[virus]),
            optogenetic_virus_injections=OptogeneticVirusInjections(viral_vector_injections=all_injections),
        )
        nwbfile.add_lab_meta_data(opto_experiment_meta)
