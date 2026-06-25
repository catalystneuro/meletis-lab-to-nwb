"""Primary script to run to convert all sessions in the reaching_test dataset."""

import csv
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from pprint import pformat

from tqdm import tqdm

from meletis_lab_to_nwb.reaching_test.convert_session import session_to_nwb


def dataset_to_nwb(
    *,
    data_dir_path: str | Path,
    output_dir_path: str | Path,
    max_workers: int = 1,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert the entire reaching_test dataset to NWB.

    Iterates rows of ``details.csv`` and dispatches one ``session_to_nwb`` job per
    session. Sessions without a manual annotation CSV (``has_behavior`` FALSE; the
    mouse performed no reach attempts) are still converted and get a video +
    pose-estimation NWB file with no reaching_events table.
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    session_kwargs_per_session = get_session_to_nwb_kwargs_per_session(data_dir_path=data_dir_path)

    futures = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for session_kwargs in session_kwargs_per_session:
            session_kwargs["output_dir_path"] = output_dir_path
            session_kwargs["stub_test"] = stub_test
            session_kwargs["verbose"] = verbose
            video_name = Path(session_kwargs["video_file_path"]).stem
            exception_file_path = output_dir_path / f"ERROR_{video_name}.txt"
            futures.append(
                executor.submit(
                    safe_session_to_nwb,
                    session_to_nwb_kwargs=session_kwargs,
                    exception_file_path=exception_file_path,
                )
            )
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Converting sessions"):
            pass


def safe_session_to_nwb(*, session_to_nwb_kwargs: dict, exception_file_path: Path | str):
    """Convert a session to NWB while recording any error to ``exception_file_path``."""
    exception_file_path = Path(exception_file_path)
    try:
        session_to_nwb(**session_to_nwb_kwargs)
    except Exception:
        exception_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(exception_file_path, mode="w") as f:
            f.write(f"session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
            f.write(traceback.format_exc())


def get_session_to_nwb_kwargs_per_session(*, data_dir_path: str | Path) -> list[dict]:
    """Build the per-session kwargs list from ``details.csv`` and the data directory layout.

    Video resolution order: ``videos_mp4/<stem>.mp4`` → ``videos/<stem>.avi``.
    Pose estimation is included only when ``has_dlc`` is TRUE and the CSV file exists.
    """
    data_dir_path = Path(data_dir_path)
    details_file_path = data_dir_path / "details.csv"

    session_kwargs_list: list[dict] = []
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_stem = (row.get("video") or "").strip()
            if not video_stem:
                continue

            # Prefer MP4 (converted from AVI) when available, fall back to AVI.
            mp4_path = data_dir_path / "videos_mp4" / f"{video_stem}.mp4"
            avi_path = data_dir_path / "videos" / f"{video_stem}.avi"
            if mp4_path.exists():
                video_file_path = mp4_path
            elif avi_path.exists():
                video_file_path = avi_path
            else:
                print(f"Warning: No video file found, skipping: {video_stem}")
                continue

            # Pose estimation is optional — only include when available.
            has_dlc = row.get("has_dlc", "").strip().upper() == "TRUE"
            pose_estimation_file_path = None
            if has_dlc:
                dlc_path = (
                    data_dir_path
                    / "pose_estimation"
                    / f"{video_stem}DLC_resnet50_reaching_trainJun9shuffle1_100000.csv"
                )
                if dlc_path.exists():
                    pose_estimation_file_path = dlc_path
                else:
                    print(f"Warning: DLC file not found (has_dlc=TRUE): {dlc_path}")

            behavior_file_path = data_dir_path / "annotations" / f"{video_stem}_behavior.csv"

            session_kwargs_list.append(
                dict(
                    video_file_path=video_file_path,
                    pose_estimation_file_path=pose_estimation_file_path,
                    behavior_file_path=behavior_file_path if behavior_file_path.exists() else None,
                    details_row=row,
                )
            )

    return session_kwargs_list


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/reaching_test")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/reaching_test")
    max_workers = 4
    stub_test = False

    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        max_workers=max_workers,
        stub_test=stub_test,
        verbose=False,
    )
