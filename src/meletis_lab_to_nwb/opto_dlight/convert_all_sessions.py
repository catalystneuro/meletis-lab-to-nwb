"""Primary script to run to convert all sessions in the opto+dLight dataset."""

import csv
import datetime
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from pprint import pformat
from zoneinfo import ZoneInfo

from tqdm import tqdm

from meletis_lab_to_nwb.opto_dlight.convert_session import session_to_nwb


def dataset_to_nwb(
    *,
    data_dir_path: str | Path,
    output_dir_path: str | Path,
    max_workers: int = 1,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert the entire opto+dLight dataset to NWB.

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
            video_name = Path(session_to_nwb_kwargs["ttl_file_path"]).stem
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
            video_name = row.get("video", "").strip()
            if not video_name:
                continue

            ttl_file_path = data_dir_path / "TTL" / f"{video_name}.csv"
            signal_file_path = data_dir_path / "signal" / f"{video_name}_signal_df.csv"

            if not ttl_file_path.exists() and not signal_file_path.exists():
                print(f"Warning: No TTL or signal file found, skipping: {video_name}")
                continue

            date_str = video_name.replace("oft_", "")
            session_date = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(
                tzinfo=ZoneInfo("Europe/Stockholm")
            )

            session_kwargs_list.append(
                dict(
                    ttl_file_path=ttl_file_path,
                    signal_file_path=signal_file_path,
                    subject_id=row["mouse.ID"],
                    session_date=session_date,
                    group=row["group"],
                    line=row["line"],
                    intensity_mw=float(row["intenisty"]),
                    frequency_hz=float(row["frequency"]),
                )
            )

    return session_kwargs_list


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/opto+dLight")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/opto_dlight")
    max_workers = 4
    stub_test = False

    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        max_workers=max_workers,
        stub_test=stub_test,
        verbose=False,
    )
