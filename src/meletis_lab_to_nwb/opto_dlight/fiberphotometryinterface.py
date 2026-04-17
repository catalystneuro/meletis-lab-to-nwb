"""DataInterface for fiber photometry signal data (opto+dLight experiment)."""

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
    """DataInterface for reading fiber photometry signal CSVs and writing to NWB via ndx-fiber-photometry.

    The signal CSVs have 2 columns: Time(s) and a motion-corrected dF/F signal column.
    The signal column name is unique per file and encodes signal/reference channel parameters.
    Sampling rate is ~60 Hz with timestamps starting at ~8s.

    The motion-corrected dF/F signal is stored as a ``DfOverFFiberPhotometryResponseSeries``
    inside the ``ophys`` processing module (``processing/ophys/``), reflecting that it is a
    processed derivative (470 nm signal minus 405 nm isosbestic reference) rather than raw
    acquisition data.

    Optionally, the raw acquisition file (*_signal.csv) with columns ``time``, ``ref``
    (405 nm isosbestic control), and ``sig`` (470 nm signal) can be provided. When supplied,
    the raw fluorescence traces are stored as ``FiberPhotometryResponseSeries`` objects in
    ``nwbfile.acquisition``.
    """

    keywords = ("fiber photometry", "dopamine")

    def __init__(self, file_path: str | Path, raw_file_path: str | Path | None = None, verbose: bool = True):
        """Initialize FiberPhotometryInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the processed dF/F signal CSV file (e.g., *_signal_df.csv).
        raw_file_path : str or Path, optional
            Path to the raw acquisition CSV file (e.g., *_signal.csv) with columns
            ``time``, ``ref`` (405 nm), and ``sig`` (470 nm). When provided, raw
            fluorescence traces are added to ``nwbfile.acquisition``.
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, raw_file_path=raw_file_path, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        fp_metadata_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        fp_metadata = load_dict_from_file(fp_metadata_path)
        metadata = dict_deep_update(metadata, fp_metadata)

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, stub_test: bool = False) -> None:
        # Read processed dF/F CSV
        df = pd.read_csv(self.source_data["file_path"])
        timestamps = df["Time(s)"].values
        signal_column = [c for c in df.columns if c != "Time(s)"][0]
        signal_data = df[signal_column].values

        # Read raw acquisition CSV (optional)
        raw_file_path = self.source_data.get("raw_file_path")
        raw_df = None
        if raw_file_path is not None:
            raw_df = pd.read_csv(raw_file_path)

        if stub_test:
            timestamps = timestamps[:300]
            signal_data = signal_data[:300]
            if raw_df is not None:
                raw_df = raw_df.iloc[:300]

        # Read metadata
        fp_meta = (metadata or {}).get("FiberPhotometry", {})
        location = fp_meta.get("location")
        indicator_label = fp_meta.get("indicator_label")
        excitation_wavelength_in_nm = fp_meta.get("excitation_wavelength_in_nm")
        emission_wavelength_in_nm = fp_meta.get("emission_wavelength_in_nm")

        # --- ExcitationSourceModel (470 nm signal channel) ---
        # wavelength_range_in_nm computed in code to avoid dict_deep_update list deduplication
        esm_470_meta = fp_meta.get("ExcitationSourceModel_470nm", {})
        excitation_source_model_signal = ExcitationSourceModel(
            name=esm_470_meta.get("name"),
            manufacturer=esm_470_meta.get("manufacturer"),
            source_type=esm_470_meta.get("source_type"),
            excitation_mode=esm_470_meta.get("excitation_mode"),
            wavelength_range_in_nm=[excitation_wavelength_in_nm, excitation_wavelength_in_nm],
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
            wavelength_range_in_nm=[wavelength_405, wavelength_405],
        )
        nwbfile.add_device_model(excitation_source_model_isosbestic)

        # --- OpticalFiberModel (Doric 400 µm cannula) ---
        ofm_meta = fp_meta.get("OpticalFiberModel", {})
        optical_fiber_model = OpticalFiberModel(
            name=ofm_meta.get("name"),
            manufacturer=ofm_meta.get("manufacturer"),
            numerical_aperture=float(ofm_meta.get("numerical_aperture")),
            core_diameter_in_um=float(ofm_meta.get("core_diameter_in_um")),
            ferrule_name=ofm_meta.get("ferrule_name"),
        )
        nwbfile.add_device_model(optical_fiber_model)

        # --- Device instances linked to their models via model= ---
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
        fiber_insertion = FiberInsertion(name=fi_meta.get("name"))
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

        nwbfile.add_device(optical_fiber)
        nwbfile.add_device(excitation_source_signal)
        nwbfile.add_device(excitation_source_isosbestic)
        nwbfile.add_device(photodetector)

        ind_meta = fp_meta.get("Indicator", {})
        ind_kwargs = dict(
            name=ind_meta.get("name"),
            label=indicator_label,
            description=ind_meta.get("description") or "",
        )
        if manufacturer := ind_meta.get("manufacturer"):
            ind_kwargs["manufacturer"] = manufacturer
        indicator = Indicator(**ind_kwargs)

        fpt_meta = fp_meta.get("FiberPhotometryTable", {})
        fiber_photometry_table = FiberPhotometryTable(
            name=fpt_meta.get("name"),
            description=fpt_meta.get("description") or "",
        )
        # Row 0: 470 nm signal channel
        fiber_photometry_table.add_row(
            location=location,
            excitation_wavelength_in_nm=excitation_wavelength_in_nm,
            emission_wavelength_in_nm=emission_wavelength_in_nm,
            indicator=indicator,
            optical_fiber=optical_fiber,
            excitation_source=excitation_source_signal,
            photodetector=photodetector,
        )
        # Row 1: 405 nm isosbestic reference channel
        fiber_photometry_table.add_row(
            location=location,
            excitation_wavelength_in_nm=wavelength_405,
            emission_wavelength_in_nm=emission_wavelength_in_nm,
            indicator=indicator,
            optical_fiber=optical_fiber,
            excitation_source=excitation_source_isosbestic,
            photodetector=photodetector,
        )

        series_meta = fp_meta.get("DfOverFFiberPhotometryResponseSeries", {})
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

        # --- Raw acquisition series (optional) ---
        if raw_df is not None:
            raw_timestamps = raw_df["time"].values

            raw_sig_meta = fp_meta.get("RawSignalFiberPhotometryResponseSeries", {})
            raw_ref_meta = fp_meta.get("RawReferenceFiberPhotometryResponseSeries", {})

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
