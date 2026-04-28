"""DataInterface for aligned analysis CSV data (kinematics)."""

from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.base import TimeSeries
from pynwb.behavior import BehavioralTimeSeries

# Kinematics columns to extract from aligned CSVs.
# Note: 'acceleration' is only present in aligned_157, not aligned_36.
KINEMATICS_COLUMNS = {
    "speed": {"description": "Movement speed of the body center.", "unit": "pixels/s"},
    "acceleration": {"description": "Movement acceleration of the body center.", "unit": "pixels/s^2"},
    "angular.speed": {"description": "Angular speed of body orientation.", "unit": "rad/s"},
    "distance.moved": {"description": "Distance moved by the body center per frame.", "unit": "pixels"},
    "angular.distance": {"description": "Angular distance of body orientation change per frame.", "unit": "rad"},
    "speed_snout": {"description": "Movement speed of the snout.", "unit": "pixels/s"},
    "distance.moved_snout": {"description": "Distance moved by the snout per frame.", "unit": "pixels"},
}


class OpenFieldTestBehaviorInterface(BaseDataInterface):
    """DataInterface for reading aligned analysis CSVs and writing computed kinematics to NWB.

    The aligned CSVs contain merged DLC pose, VAME motifs, kinematics, photometry signal,
    and metadata at 30 Hz. This interface extracts only the kinematics columns (speed,
    acceleration, angular speed, distances) since other data streams are handled by their
    own dedicated interfaces.
    """

    keywords = ("kinematics", "speed", "acceleration", "locomotion")

    def __init__(self, file_path: str | Path, verbose: bool = True):
        """Initialize OpenFieldTestBehaviorInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the aligned analysis CSV file.
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
        self.file_path = Path(file_path)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **kwargs) -> None:
        df = pd.read_csv(self.file_path)

        behavior_module = nwbfile.processing.get("behavior")
        if behavior_module is None:
            behavior_module = nwbfile.create_processing_module(
                name="behavior", description="Processed behavioral data."
            )

        behavioral_time_series = BehavioralTimeSeries(name="Kinematics")

        for col_name, col_info in KINEMATICS_COLUMNS.items():
            if col_name not in df.columns:
                continue

            data = df[col_name].values.astype(np.float64)
            # Replace NaN with 0.0 for NWB compatibility
            # data = np.nan_to_num(data, nan=0.0)

            # Convert column name with dots to valid NWB name
            series_name = col_name.replace(".", "_")
            ts = TimeSeries(
                name=series_name,
                data=data,
                rate=30.0,
                unit=col_info["unit"],
                description=col_info["description"],
            )
            behavioral_time_series.add_timeseries(ts)

        behavior_module.add(behavioral_time_series)
