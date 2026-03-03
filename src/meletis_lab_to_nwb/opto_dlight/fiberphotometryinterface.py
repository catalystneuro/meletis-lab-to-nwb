"""DataInterface for fiber photometry signal data (opto+dLight experiment)."""

from pathlib import Path

import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from pynwb import NWBFile


class FiberPhotometryInterface(BaseDataInterface):
    """DataInterface for reading fiber photometry signal CSVs and writing to NWB via ndx-fiber-photometry.

    The signal CSVs have 2 columns: Time(s) and a motion-corrected dF/F signal column.
    The signal column name is unique per file and encodes signal/reference channel parameters.
    Sampling rate is ~60 Hz with timestamps starting at ~8s.
    """

    keywords = ("fiber photometry", "photometry", "dLight", "dopamine")

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
        self.file_path = Path(file_path)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, stub_test: bool = False) -> None:
        from ndx_fiber_photometry import (
            FiberPhotometry,
            FiberPhotometryIndicators,
            FiberPhotometryResponseSeries,
            FiberPhotometryTable,
        )
        from ndx_ophys_devices import (
            ExcitationSource,
            FiberInsertion,
            Indicator,
            OpticalFiber,
            Photodetector,
        )

        df = pd.read_csv(self.file_path)
        timestamps = df["Time(s)"].values
        signal_column = [c for c in df.columns if c != "Time(s)"][0]
        signal_data = df[signal_column].values

        if stub_test:
            timestamps = timestamps[:300]
            signal_data = signal_data[:300]

        # Determine recording location from metadata
        fp_meta = metadata.get("FiberPhotometry", {}) if metadata else {}
        location = fp_meta.get("location", "striatum")
        indicator_label = fp_meta.get("indicator_label", "dLight1.3b")

        indicator = Indicator(
            name="indicator",
            description=f"Dopamine indicator ({indicator_label}).",
            label=indicator_label,
        )

        fiber_insertion = FiberInsertion(name="fiber_insertion")
        optical_fiber = OpticalFiber(
            name="optical_fiber",
            description="Optical fiber for photometry recording.",
            fiber_insertion=fiber_insertion,
        )
        excitation_source = ExcitationSource(
            name="excitation_source",
            description="470 nm LED excitation source.",
        )
        photodetector = Photodetector(
            name="photodetector",
            description="Photodetector for fiber photometry.",
        )

        nwbfile.add_device(optical_fiber)
        nwbfile.add_device(excitation_source)
        nwbfile.add_device(photodetector)

        fiber_photometry_table = FiberPhotometryTable(
            name="fiber_photometry_table",
            description="Fiber photometry metadata table.",
        )
        fiber_photometry_table.add_row(
            location=location,
            excitation_wavelength_in_nm=470.0,
            emission_wavelength_in_nm=525.0,
            indicator=indicator,
            optical_fiber=optical_fiber,
            excitation_source=excitation_source,
            photodetector=photodetector,
        )

        table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            region=[0],
            description="Fiber photometry channel.",
        )

        response_series = FiberPhotometryResponseSeries(
            name="FiberPhotometryResponseSeries",
            description=(
                f"Motion-corrected fiber photometry signal (sig - ref). "
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
        nwbfile.add_acquisition(response_series)
