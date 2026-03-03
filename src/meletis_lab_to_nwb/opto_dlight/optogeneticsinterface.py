"""DataInterface for optogenetic stimulation TTL data."""

from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite


class OptogeneticsTTLInterface(BaseDataInterface):
    """DataInterface for reading optogenetic stimulation TTL CSVs and writing to NWB.

    The TTL CSVs have 3 columns (no header): ISO timestamp, sample index, and boolean (True/False)
    indicating whether the laser was on at each ~30 Hz sample. The first burst of True values
    corresponds to fiber photometry system activation and is excluded from the optogenetic data.

    Stimulation episodes are extracted by grouping consecutive True samples separated by gaps > 1s.
    Each episode represents a nosepoke-triggered bilateral SNc laser stimulation (40 Hz, 1s on / 3s off).
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

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
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

        # Trim data: start from just before the first real stimulation
        # Keep a small buffer (1s) before the first stim episode for baseline
        buffer_samples = int(30)  # ~1s at 30 Hz
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
        rate = 1.0 / np.median(np.diff(time_seconds[:1000]))

        device = Device(
            name="laser",
            description="Bilateral laser for optogenetic stimulation of SNc dopamine neurons.",
        )
        nwbfile.add_device(device)

        ogen_site = OptogeneticStimulusSite(
            name="OptogeneticStimulusSite",
            description=(
                f"Bilateral SNc optogenetic stimulation site. "
                f"Laser frequency: {frequency_hz} Hz, intensity: {intensity_mw} mW."
            ),
            device=device,
            excitation_lambda=473.0,
            location="SNc",
        )
        nwbfile.add_ogen_site(ogen_site)

        ogen_series = OptogeneticSeries(
            name="OptogeneticSeries",
            description=(
                f"Optogenetic stimulation TTL trace. Values represent laser power in watts "
                f"({intensity_mw} mW = {intensity_w} W when on, 0 when off). Protocol: {frequency_hz} Hz, "
                f"1s stimulation triggered by nosepoke with 3s inter-stimulation interval. "
                f"The first TTL burst (fiber photometry system activation) has been excluded."
            ),
            data=trimmed_power,
            rate=rate,
            starting_time=starting_time,
            site=ogen_site,
        )
        nwbfile.add_stimulus(ogen_series)

        # Also add stimulation episodes as TimeIntervals
        stim_intervals = nwbfile.create_time_intervals(
            name="stimulation_episodes",
            description=(
                "Nosepoke-triggered optogenetic stimulation episodes. Each row represents one "
                "stimulation burst (1s of laser at the session's frequency/intensity). "
                "The first TTL burst (fiber photometry system activation) is excluded."
            ),
        )

        # Extract episode onset/offset times (skip first burst)
        for burst_idx in range(1, len(burst_starts)):
            b_start = burst_starts[burst_idx]
            b_end = burst_starts[burst_idx + 1] if burst_idx + 1 < len(burst_starts) else len(true_indices)
            episode_onset = true_times[b_start]
            episode_offset = true_times[b_end - 1]
            stim_intervals.add_row(start_time=episode_onset, stop_time=episode_offset)
