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
    """

    keywords = ("fiber photometry", "dopamine")

    def __init__(self, file_path: str | Path, verbose: bool = True):
        """Initialize FiberPhotometryInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the signal CSV file (e.g., *_signal_df.csv).
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        fp_metadata_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        fp_metadata = load_dict_from_file(fp_metadata_path)
        metadata = dict_deep_update(metadata, fp_metadata)

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, stub_test: bool = False) -> None:
        # Read signal CSV
        df = pd.read_csv(self.source_data["file_path"])
        timestamps = df["Time(s)"].values
        signal_column = [c for c in df.columns if c != "Time(s)"][0]
        signal_data = df[signal_column].values

        if stub_test:
            timestamps = timestamps[:300]
            signal_data = signal_data[:300]

        # Read metadata
        fp_meta = (metadata or {}).get("FiberPhotometry", {})
        location = fp_meta.get("location", "unknown")
        indicator_label = fp_meta.get("indicator_label", "dLight1.3b")
        excitation_wavelength_in_nm = fp_meta.get("excitation_wavelength_in_nm", 470.0)
        emission_wavelength_in_nm = fp_meta.get("emission_wavelength_in_nm", 525.0)

        # --- ExcitationSourceModel (470 nm signal channel) ---
        # wavelength_range_in_nm computed in code to avoid dict_deep_update list deduplication
        esm_470_meta = fp_meta.get("ExcitationSourceModel_470nm", {})
        excitation_source_model_signal = ExcitationSourceModel(
            name=esm_470_meta.get("name", "doric_470nm_led_model"),
            manufacturer=esm_470_meta.get("manufacturer", "Doric"),
            source_type=esm_470_meta.get("source_type", "LED"),
            excitation_mode=esm_470_meta.get("excitation_mode", "one-photon"),
            wavelength_range_in_nm=[excitation_wavelength_in_nm, excitation_wavelength_in_nm],
        )
        nwbfile.add_device_model(excitation_source_model_signal)

        # --- ExcitationSourceModel (405 nm isosbestic reference channel) ---
        esm_405_meta = fp_meta.get("ExcitationSourceModel_405nm", {})
        wavelength_405 = float(esm_405_meta.get("wavelength_in_nm", 405.0))
        excitation_source_model_isosbestic = ExcitationSourceModel(
            name=esm_405_meta.get("name", "doric_405nm_led_model"),
            manufacturer=esm_405_meta.get("manufacturer", "Doric"),
            source_type=esm_405_meta.get("source_type", "LED"),
            excitation_mode=esm_405_meta.get("excitation_mode", "one-photon"),
            wavelength_range_in_nm=[wavelength_405, wavelength_405],
        )
        nwbfile.add_device_model(excitation_source_model_isosbestic)

        # --- OpticalFiberModel (Doric 400 µm cannula) ---
        ofm_meta = fp_meta.get("OpticalFiberModel", {})
        optical_fiber_model = OpticalFiberModel(
            name=ofm_meta.get("name", "doric_400um_cannula_model"),
            manufacturer=ofm_meta.get("manufacturer", "Doric"),
            numerical_aperture=float(ofm_meta.get("numerical_aperture", 0.22)),
            core_diameter_in_um=float(ofm_meta.get("core_diameter_in_um", 400.0)),
            ferrule_name=ofm_meta.get("ferrule_name", "ceramic ferrule"),
        )
        nwbfile.add_device_model(optical_fiber_model)

        # --- Device instances linked to their models via model= ---
        es_signal_meta = fp_meta.get("ExcitationSourceSignal", {})
        excitation_source_signal = ExcitationSource(
            name=es_signal_meta.get("name", "excitation_source_signal"),
            description=es_signal_meta.get(
                "description", f"{excitation_wavelength_in_nm:.0f} nm LED excitation source."
            ),
            model=excitation_source_model_signal,
        )

        es_isos_meta = fp_meta.get("ExcitationSourceIsosbestic", {})
        excitation_source_isosbestic = ExcitationSource(
            name=es_isos_meta.get("name", "excitation_source_isosbestic"),
            description=es_isos_meta.get("description", f"{wavelength_405:.0f} nm LED isosbestic reference."),
            model=excitation_source_model_isosbestic,
        )

        of_meta = fp_meta.get("OpticalFiber", {})
        fiber_insertion = FiberInsertion(name="fiber_insertion")
        optical_fiber = OpticalFiber(
            name=of_meta.get("name", "optical_fiber"),
            description=of_meta.get("description", "Optical fiber for photometry recording."),
            fiber_insertion=fiber_insertion,
            model=optical_fiber_model,
        )

        pd_meta = fp_meta.get("Photodetector", {})
        photodetector = Photodetector(
            name=pd_meta.get("name", "photodetector"),
            description=pd_meta.get("description", "Photodetector for fiber photometry."),
        )

        nwbfile.add_device(optical_fiber)
        nwbfile.add_device(excitation_source_signal)
        nwbfile.add_device(excitation_source_isosbestic)
        nwbfile.add_device(photodetector)

        ind_meta = fp_meta.get("Indicator", {})
        ind_kwargs = dict(
            name="indicator",
            label=indicator_label,
            description=ind_meta.get("description", f"Dopamine indicator ({indicator_label})."),
        )
        if manufacturer := ind_meta.get("manufacturer"):
            ind_kwargs["manufacturer"] = manufacturer
        indicator = Indicator(**ind_kwargs)

        fiber_photometry_table = FiberPhotometryTable(
            name="fiber_photometry_table",
            description="Fiber photometry metadata table.",
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

        table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            region=[0],
            description="Fiber photometry channel.",
        )

        series_meta = fp_meta.get("DfOverFFiberPhotometryResponseSeries", {})
        response_series = FiberPhotometryResponseSeries(
            name=series_meta.get("name", "DfOverFFiberPhotometryResponseSeries"),
            description=(
                f"Motion-corrected dF/F fiber photometry signal "
                f"(470 nm signal minus 405 nm isosbestic reference). "
                f"Indicator: {indicator_label}. Original column: {signal_column}"
            ),
            data=signal_data,
            timestamps=timestamps,
            unit="a.u.",
            fiber_photometry_table_region=table_region,
        )

        fiber_photometry_indicators = FiberPhotometryIndicators(indicators=[indicator])
        fiber_photometry_lab_meta_data = FiberPhotometry(
            name="fiber_photometry",
            fiber_photometry_table=fiber_photometry_table,
            fiber_photometry_indicators=fiber_photometry_indicators,
        )
        nwbfile.add_lab_meta_data(fiber_photometry_lab_meta_data)

        pm_meta = fp_meta.get("ProcessingModule", {})
        ophys_module = get_module(
            nwbfile,
            name=pm_meta.get("name", "ophys"),
            description=pm_meta.get(
                "description",
                "Processed optical physiology data. Contains motion-corrected dF/F signals "
                "from striatal dLight1.3b fiber photometry recordings.",
            ),
        )
        ophys_module.add(response_series)
