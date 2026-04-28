"""Primary script to run to convert all sessions in the open field test dataset."""

import csv
import datetime
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from pprint import pformat
from zoneinfo import ZoneInfo

import pandas as pd
from tqdm import tqdm

from meletis_lab_to_nwb.open_field_test.convert_session import session_to_nwb


def dataset_to_nwb(
    *,
    data_dir_path: str | Path,
    output_dir_path: str | Path,
    max_workers: int = 1,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert the entire open field test dataset to NWB.

    Parameters
    ----------
    data_dir_path : str or Path
        The path to the directory containing the raw data.
    output_dir_path : str or Path
        The path to the directory where the NWB files will be saved.
    max_workers : int, optional
        The number of workers to use for parallel processing, by default 1.
    stub_test : bool, optional
        If True, only convert a small amount of data for testing, by default False.
    verbose : bool, optional
        Whether to print verbose output, by default True.
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(data_dir_path=data_dir_path)

    futures = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for session_to_nwb_kwargs in session_to_nwb_kwargs_per_session:
            session_to_nwb_kwargs["output_dir_path"] = output_dir_path
            session_to_nwb_kwargs["stub_test"] = stub_test
            session_to_nwb_kwargs["verbose"] = verbose
            video_name = Path(session_to_nwb_kwargs["video_file_path"]).stem
            exception_file_path = output_dir_path / f"ERROR_{video_name}.txt"
            futures.append(
                executor.submit(
                    safe_session_to_nwb,
                    session_to_nwb_kwargs=session_to_nwb_kwargs,
                    exception_file_path=exception_file_path,
                )
            )
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Converting sessions"):
            pass


def safe_session_to_nwb(*, session_to_nwb_kwargs: dict, exception_file_path: Path | str):
    """Convert a session to NWB while handling any errors by recording error messages to the exception_file_path."""
    exception_file_path = Path(exception_file_path)
    try:
        session_to_nwb(**session_to_nwb_kwargs)
    except Exception:
        exception_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(exception_file_path, mode="w") as f:
            f.write(f"session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
            f.write(traceback.format_exc())


def _parse_session_date(video_name: str) -> datetime.datetime:
    """Parse session datetime from video filename, handling both oft_ and tmaze_ prefixes."""
    if video_name.startswith("oft_"):
        date_str = video_name[4:]
    elif video_name.startswith("tmaze_"):
        date_str = video_name[6:]
    else:
        raise ValueError(f"Unexpected video name prefix: {video_name}")
    return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(tzinfo=ZoneInfo("Europe/Stockholm"))


def _get_sex_from_aligned(aligned_file_path: Path) -> str:
    """Extract subject sex from aligned CSV if available."""
    try:
        df = pd.read_csv(aligned_file_path, nrows=1)
        if "sex" in df.columns:
            sex = df["sex"].iloc[0]
            if isinstance(sex, str) and sex.lower() in ("m", "f"):
                return sex.upper()
    except Exception:
        pass
    return "U"


def get_session_to_nwb_kwargs_per_session(*, data_dir_path: str | Path) -> list[dict]:
    """Get the kwargs for session_to_nwb for each session in the dataset.

    Parameters
    ----------
    data_dir_path : str or Path
        The path to the directory containing the raw data.

    Returns
    -------
    list[dict]
        A list of dictionaries containing the kwargs for session_to_nwb for each session.
    """
    data_dir_path = Path(data_dir_path)
    details_file_path = data_dir_path / "details.csv"

    session_kwargs_list = []
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_name = row["video"]
            video_file_path = data_dir_path / "videos" / f"{video_name}.mp4"
            pose_estimation_file_path = data_dir_path / "pose_estimation" / f"{video_name}.csv"

            if not video_file_path.exists():
                print(f"Warning: Video file not found, skipping: {video_file_path}")
                continue
            if not pose_estimation_file_path.exists():
                print(f"Warning: Pose estimation file not found, skipping: {pose_estimation_file_path}")
                continue

            session_date = _parse_session_date(video_name)

            # Check for optional data streams
            vame_157_path = data_dir_path / "vame_157" / f"47_km_label_{video_name}.npy"
            vame_36_path = data_dir_path / "vame_36" / f"47_km_label_{video_name}.npy"
            signal_path = data_dir_path / "signal" / f"{video_name}_signal_df.csv"
            aligned_157_path = data_dir_path / "aligned_157" / f"{video_name}_aligned.csv"

            # Get sex from aligned CSV if available
            sex = _get_sex_from_aligned(aligned_157_path) if aligned_157_path.exists() else "U"

            session_kwargs_list.append(
                dict(
                    video_file_path=video_file_path,
                    pose_estimation_file_path=pose_estimation_file_path,
                    subject_id=row["mouse.ID"],
                    session_date=session_date,
                    group=row["group"],
                    line=row["line"],
                    experiment=row["experiment"],
                    vame_157_file_path=vame_157_path if vame_157_path.exists() else None,
                    vame_36_file_path=vame_36_path if vame_36_path.exists() else None,
                    signal_file_path=signal_path if signal_path.exists() else None,
                    aligned_file_path=aligned_157_path if aligned_157_path.exists() else None,
                    sex=sex,
                    ctrl_vs_exp=row.get("ctrl.vs.exp"),
                )
            )

    return session_kwargs_list


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/oft")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/open_field_test")
    max_workers = 4
    stub_test = False

    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        max_workers=max_workers,
        stub_test=stub_test,
        verbose=False,
    )
