"""Base DataInterface for Doric fiber photometry signal data.

This module provides a shared implementation for all Meletis-lab fiber photometry
conversions (opto+dLight, water consumption / forelimb reaching, open field test).
The recording hardware and CSV format are identical across experiments:

* Processed dF/F CSV (``*_signal_df.csv``): ``Time(s)`` + one signal column.
* Optional raw acquisition CSV (``*_signal.csv``): ``time``, ``ref`` (405 nm), ``sig`` (470 nm).
* Same Doric system: interleaved 470/405 nm LED excitation at ~60 Hz (DoricStudio V5).

Each conversion subclass must implement :meth:`get_metadata` to load its own
``fiber_photometry_metadata.yaml`` file (different per-experiment descriptions, indicators,
and recording-site notes). The :meth:`add_to_nwbfile` implementation is shared.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ndx_fiber_photometry import (
    FiberPhotometry,
    FiberPhotometryIndicators,
    FiberPhotometryResponseSeries,
    FiberPhotometryTable,
)
from ndx_ophys_devices import (
    ExcitationSource,
    ExcitationSourceModel,
    FiberInsertion,
    Indicator,
    OpticalFiber,
    OpticalFiberModel,
    Photodetector,
)
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict, dict_deep_update, load_dict_from_file
from pynwb import NWBFile


class FiberPhotometryInterface(BaseDataInterface):
    """Abstract base interface for Doric fiber photometry recordings.

    All fiber photometry conversions in this repository share the same hardware
    (Doric LED system, DoricStudio V5 preprocessing) and CSV format. Subclasses
    must implement :meth:`get_metadata` to load their conversion-specific
    ``fiber_photometry_metadata.yaml``.

    Parameters
    ----------
    file_path : str or Path
        Path to the processed dF/F signal CSV file (``*_signal_df.csv``).
    raw_file_path : str or Path, optional
        Path to the raw acquisition CSV file (``*_signal.csv``) with columns
        ``time``, ``ref`` (405 nm), and ``sig`` (470 nm). When provided, raw
        fluorescence traces are stored in ``nwbfile.acquisition``.
    verbose : bool, optional
        Whether to print verbose output, by default True.
    """

    keywords = ("fiber photometry", "fluorescence", "dopamine")

    def __init__(
        self,
        file_path: str | Path,
        raw_file_path: str | Path | None = None,
        metadata_yaml_path: str | Path | None = None,
        verbose: bool = True,
    ):
        self.metadata_yaml_path = Path(metadata_yaml_path)
        super().__init__(file_path=file_path, raw_file_path=raw_file_path, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self.metadata_yaml_path.exists():
            editable_metadata = load_dict_from_file(self.metadata_yaml_path)
            metadata = dict_deep_update(metadata, editable_metadata)
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, stub_test: bool = False) -> None:
        """Write fiber photometry data to an NWB file.

        Reads the processed dF/F CSV and (optionally) the raw acquisition CSV, then
        creates all required ndx-fiber-photometry and ndx-ophys-devices objects from
        ``metadata["FiberPhotometry"]``. The dF/F series is stored inside the
        ``ophys`` processing module; raw series go into ``nwbfile.acquisition``.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Full metadata dict (from :meth:`get_metadata` after per-session overrides).
        stub_test : bool, optional
            If True, only the first 300 samples are written. Default False.
        """
        # --- Read processed dF/F CSV ---
        df = pd.read_csv(self.source_data["file_path"])
        timestamps = df["Time(s)"].values
        signal_column = [c for c in df.columns if c != "Time(s)"][0]
        signal_data = df[signal_column].values

        # --- Read raw acquisition CSV (optional) ---
        raw_file_path = self.source_data.get("raw_file_path")
        raw_df = None
        if raw_file_path is not None:
            raw_df = pd.read_csv(raw_file_path)

        if stub_test:
            timestamps = timestamps[:300]
            signal_data = signal_data[:300]
            if raw_df is not None:
                raw_df = raw_df.iloc[:300]

        # --- Read metadata ---
        fp_meta = (metadata or {}).get("FiberPhotometry", {})
        location = fp_meta.get("location")
        indicator_label = fp_meta.get("indicator_label")
        excitation_wavelength_in_nm = fp_meta.get("excitation_wavelength_in_nm")
        emission_wavelength_in_nm = fp_meta.get("emission_wavelength_in_nm")

        # --- ExcitationSourceModel (470 nm signal channel) ---
        esm_470_meta = fp_meta.get("ExcitationSourceModel_470nm", {})
        excitation_source_model_signal = ExcitationSourceModel(
            name=esm_470_meta.get("name"),
            manufacturer=esm_470_meta.get("manufacturer"),
            source_type=esm_470_meta.get("source_type"),
            excitation_mode=esm_470_meta.get("excitation_mode"),
            wavelength_range_in_nm=esm_470_meta.get("wavelength_range_in_nm"),
        )
        nwbfile.add_device_model(excitation_source_model_signal)

        # --- ExcitationSourceModel (405 nm isosbestic reference channel) ---
        esm_405_meta = fp_meta.get("ExcitationSourceModel_405nm", {})
        wavelength_405 = float(esm_405_meta.get("wavelength_in_nm"))
        excitation_source_model_isosbestic = ExcitationSourceModel(
            name=esm_405_meta.get("name"),
            manufacturer=esm_405_meta.get("manufacturer"),
            source_type=esm_405_meta.get("source_type"),
            excitation_mode=esm_405_meta.get("excitation_mode"),
            wavelength_range_in_nm=esm_405_meta.get("wavelength_range_in_nm"),
        )
        nwbfile.add_device_model(excitation_source_model_isosbestic)

        # --- OpticalFiberModel ---
        ofm_meta = fp_meta.get("OpticalFiberModel", {})
        optical_fiber_model = OpticalFiberModel(
            name=ofm_meta.get("name"),
            manufacturer=ofm_meta.get("manufacturer"),
            numerical_aperture=float(ofm_meta.get("numerical_aperture")),
            core_diameter_in_um=float(ofm_meta.get("core_diameter_in_um")),
            ferrule_name=ofm_meta.get("ferrule_name"),
        )
        nwbfile.add_device_model(optical_fiber_model)

        # --- Device instances linked to their models ---
        es_signal_meta = fp_meta.get("ExcitationSourceSignal", {})
        excitation_source_signal = ExcitationSource(
            name=es_signal_meta.get("name"),
            description=es_signal_meta.get("description") or "",
            model=excitation_source_model_signal,
        )

        es_isos_meta = fp_meta.get("ExcitationSourceIsosbestic", {})
        excitation_source_isosbestic = ExcitationSource(
            name=es_isos_meta.get("name"),
            description=es_isos_meta.get("description") or "",
            model=excitation_source_model_isosbestic,
        )

        of_meta = fp_meta.get("OpticalFiber", {})
        fi_meta = fp_meta.get("FiberInsertion", {})
        fi_kwargs = dict(name=fi_meta.get("name", "fiber_insertion"))
        for coord_key in (
            "insertion_position_ap_in_mm",
            "insertion_position_ml_in_mm",
            "insertion_position_dv_in_mm",
            "position_reference",
            "hemisphere",
        ):
            if (val := fi_meta.get(coord_key)) is not None:
                fi_kwargs[coord_key] = val
        fiber_insertion = FiberInsertion(**fi_kwargs)
        optical_fiber = OpticalFiber(
            name=of_meta.get("name"),
            description=of_meta.get("description") or "",
            fiber_insertion=fiber_insertion,
            model=optical_fiber_model,
        )

        pd_meta = fp_meta.get("Photodetector", {})
        photodetector = Photodetector(
            name=pd_meta.get("name"),
            description=pd_meta.get("description") or "",
        )

        nwbfile.add_device(excitation_source_signal)
        nwbfile.add_device(excitation_source_isosbestic)
        nwbfile.add_device(optical_fiber)
        nwbfile.add_device(photodetector)

        # --- Indicator ---
        ind_meta = fp_meta.get("Indicator", {})
        ind_kwargs = dict(
            name=ind_meta.get("name"),
            label=indicator_label,
            description=ind_meta.get("description") or "",
        )
        if manufacturer := ind_meta.get("manufacturer"):
            ind_kwargs["manufacturer"] = manufacturer
        indicator = Indicator(**ind_kwargs)

        # --- FiberPhotometryTable (row 0: 470 nm signal; row 1: 405 nm reference) ---
        fpt_meta = fp_meta.get("FiberPhotometryTable", {})
        fiber_photometry_table = FiberPhotometryTable(
            name=fpt_meta.get("name"),
            description=fpt_meta.get("description") or "",
        )
        fiber_photometry_table.add_row(
            location=location,
            excitation_wavelength_in_nm=excitation_wavelength_in_nm,
            emission_wavelength_in_nm=emission_wavelength_in_nm,
            indicator=indicator,
            optical_fiber=optical_fiber,
            excitation_source=excitation_source_signal,
            photodetector=photodetector,
        )
        fiber_photometry_table.add_row(
            location=location,
            excitation_wavelength_in_nm=wavelength_405,
            emission_wavelength_in_nm=emission_wavelength_in_nm,
            indicator=indicator,
            optical_fiber=optical_fiber,
            excitation_source=excitation_source_isosbestic,
            photodetector=photodetector,
        )

        # --- Processed dF/F series → ophys processing module ---
        series_meta = fp_meta.get("FiberPhotometrySeriesDfOverF", {})
        dff_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            region=[0],
            description=series_meta.get("table_region_description") or "",
        )
        response_series = FiberPhotometryResponseSeries(
            name=series_meta.get("name"),
            description=(series_meta.get("description") or "").format(
                indicator_label=indicator_label, signal_column=signal_column
            ),
            data=signal_data,
            timestamps=timestamps,
            unit="a.u.",
            fiber_photometry_table_region=dff_table_region,
        )

        fp_lab_meta = fp_meta.get("FiberPhotometryLabMetaData", {})
        fiber_photometry_indicators = FiberPhotometryIndicators(indicators=[indicator])
        fiber_photometry_lab_meta_data = FiberPhotometry(
            name=fp_lab_meta.get("name"),
            fiber_photometry_table=fiber_photometry_table,
            fiber_photometry_indicators=fiber_photometry_indicators,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_lab_meta_data)

        pm_meta = fp_meta.get("ProcessingModule", {})
        ophys_module = get_module(
            nwbfile,
            name=pm_meta.get("name"),
            description=pm_meta.get("description") or "",
        )
        ophys_module.add(response_series)

        # --- Raw acquisition series (optional) → nwbfile.acquisition ---
        if raw_df is not None:
            raw_timestamps = raw_df["time"].values

            raw_sig_meta = fp_meta.get("FiberPhotometrySeriesRawSignal", {})
            raw_ref_meta = fp_meta.get("FiberPhotometrySeriesIsosbesticControl", {})

            sig_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                region=[0],
                description=raw_sig_meta.get("table_region_description") or "",
            )
            ref_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                region=[1],
                description=raw_ref_meta.get("table_region_description") or "",
            )

            raw_sig_series = FiberPhotometryResponseSeries(
                name=raw_sig_meta.get("name"),
                description=raw_sig_meta.get("description") or "",
                data=raw_df["sig"].values,
                timestamps=raw_timestamps,
                unit="a.u.",
                fiber_photometry_table_region=sig_table_region,
            )
            raw_ref_series = FiberPhotometryResponseSeries(
                name=raw_ref_meta.get("name"),
                description=raw_ref_meta.get("description") or "",
                data=raw_df["ref"].values,
                timestamps=raw_timestamps,
                unit="a.u.",
                fiber_photometry_table_region=ref_table_region,
            )

            nwbfile.add_acquisition(raw_sig_series)
            nwbfile.add_acquisition(raw_ref_series)
