"""Batch runner: convert every session in details.csv to NWB in parallel."""

import csv
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from pprint import pformat

from tqdm import tqdm

from .convert_session import session_to_nwb


def dataset_to_nwb(
    *,
    data_dir_path: str | Path,
    output_dir_path: str | Path,
    max_workers: int = 1,
    verbose: bool = False,
):
    """Convert the entire water-consumption dataset to NWB.

    Parameters
    ----------
    data_dir_path : str or Path
        Path to the directory containing ``details.csv`` and the ``signal/``, ``signal_df/``,
        ``annotations/``, and ``videos/`` subfolders.
    output_dir_path : str or Path
        Directory for the output NWB files.
    max_workers : int, optional
        Number of parallel workers, by default 1.
    verbose : bool, optional
        Whether to print per-session progress, by default False.
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    session_kwargs_list = get_session_to_nwb_kwargs_per_session(data_dir_path=data_dir_path)

    futures = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for session_kwargs in session_kwargs_list:
            session_kwargs["output_dir_path"] = output_dir_path
            session_kwargs["verbose"] = verbose
            stem = session_kwargs["details_row"]["video"]
            exception_file_path = output_dir_path / f"ERROR_{stem}.txt"
            futures.append(
                executor.submit(
                    safe_session_to_nwb,
                    session_to_nwb_kwargs=session_kwargs,
                    exception_file_path=exception_file_path,
                )
            )
        for _ in tqdm(as_completed(futures), total=len(futures)):
            pass


def safe_session_to_nwb(*, session_to_nwb_kwargs: dict, exception_file_path: Path | str):
    """Run ``session_to_nwb`` and write any traceback to ``exception_file_path`` on failure."""
    exception_file_path = Path(exception_file_path)
    try:
        session_to_nwb(**session_to_nwb_kwargs)
    except Exception:
        with open(exception_file_path, mode="w") as f:
            f.write(f"session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
            f.write(traceback.format_exc())


def get_session_to_nwb_kwargs_per_session(*, data_dir_path: str | Path) -> list[dict]:
    """Build one session_to_nwb kwargs dict per row of details.csv.

    Skips sessions whose required input files are missing. Logs a warning for each skipped
    session so the user can follow up.
    """
    data_dir_path = Path(data_dir_path)
    details_file_path = data_dir_path / "details.csv"

    session_kwargs_list: list[dict] = []
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_stem = row["video"]
            signal_file_path = data_dir_path / "signal_df" / f"{video_stem}_signal_df.csv"
            raw_signal_file_path = data_dir_path / "signal" / f"{video_stem}_signal.csv"
            behavior_file_path = data_dir_path / "annotations" / f"{video_stem}_behavior.csv"
            video_file_path = data_dir_path / "videos" / f"{video_stem}.avi"

            if not signal_file_path.exists() or not behavior_file_path.exists():
                print(f"[skip] {video_stem}: missing required signal_df or annotation file")
                continue

            session_kwargs_list.append(
                dict(
                    signal_file_path=signal_file_path,
                    raw_signal_file_path=raw_signal_file_path if raw_signal_file_path.exists() else None,
                    behavior_file_path=behavior_file_path,
                    video_file_path=video_file_path if video_file_path.exists() else None,
                    details_row=row,
                    stub_test=False,
                )
            )
    return session_kwargs_list


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/water_consumption")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/water_consumption")
    max_workers = 4
    verbose = False

    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        max_workers=max_workers,
        verbose=verbose,
    )
