"""Primary script to run to convert a single session of arrow maze choice task data."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv.datainterfaces.behavior.video.video_utils import get_video_timestamps
from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.arrow_maze_choice_task import ArrowMazeChoiceTaskNWBConverter


def session_to_nwb(
    *,
    video_file_path: str | Path,
    pose_estimation_file_path: str | Path,
    output_dir_path: str | Path,
    details_row: dict,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single arrow maze choice task session to NWB.

    Parameters
    ----------
    video_file_path : str or Path
        Path to the session video file (.mp4).
    pose_estimation_file_path : str or Path
        Path to the DeepLabCut pose estimation output (.csv).
    output_dir_path : str or Path
        Path to the directory where the NWB file will be saved.
    details_row : dict
        A dictionary containing session details from the details.csv file, with
        keys like "mouse.ID", "DoB", "sex", "line", "day", "experiment", and "video".
    stub_test : bool, optional
        If True, only convert a small amount of data for testing, by default False.
    verbose : bool, optional
        If True, print verbose output, by default True.
    """
    video_file_path = Path(video_file_path)
    pose_estimation_file_path = Path(pose_estimation_file_path)

    subject_id = details_row["mouse.ID"].replace("_", "-")

    output_dir_path = Path(output_dir_path) / f"sub-{subject_id}"
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    video_name = video_file_path.stem
    session_id = video_name.replace("_", "-")
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    source_data = dict(
        Video=dict(file_paths=[video_file_path]),
        PoseEstimation=dict(file_path=str(pose_estimation_file_path)),
    )
    conversion_options = dict(
        Video=dict(),
        PoseEstimation=dict(),
    )

    converter = ArrowMazeChoiceTaskNWBConverter(source_data=source_data, verbose=verbose)

    # Set timestamps for DLC from the video file — without a config file, the interface
    # falls back to using the CSV row index [0, 1, 2, ...] which gives rate=1.0.
    timestamps = np.array(get_video_timestamps(video_file_path, display_progress=True))
    converter.data_interface_objects["PoseEstimation"].set_aligned_timestamps(timestamps)

    metadata = converter.get_metadata()

    t_zone = ZoneInfo("Europe/Stockholm")
    session_start_time = datetime.datetime.strptime(video_name, "tmaze_%Y-%m-%dT%H_%M_%S").replace(tzinfo=t_zone)
    metadata["NWBFile"]["session_start_time"] = session_start_time
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    date_of_birth = datetime.datetime.strptime(details_row["DoB"], "%d-%b-%y").replace(tzinfo=t_zone)
    metadata["Subject"].update(
        subject_id=subject_id,
        sex=details_row.get("sex", "u").upper(),
        genotype=details_row.get("line", ""),
        date_of_birth=date_of_birth,
    )

    # Update camera device from behavior_metadata.yaml
    behavior_metadata_path = Path(__file__).parent / "behavior_metadata.yaml"
    video_device = load_dict_from_file(behavior_metadata_path)["VideoDevice"]
    video_key = f"Video {video_file_path.stem}"
    metadata["Behavior"]["ExternalVideos"][video_key]["device"]["name"] = video_device["name"]
    metadata["Behavior"]["ExternalVideos"][video_key]["device"]["description"] = video_device["description"]

    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )

    if verbose:
        print(f"Converted {nwbfile_path} successfully.")


if __name__ == "__main__":
    import csv

    data_dir_path = Path("/Volumes/T9/data/Meletis/tmaze")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/arrow_maze_choice_task")
    stub_test = False

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)

    video_name = row["video"]
    session_to_nwb(
        video_file_path=data_dir_path / "videos" / f"{video_name}.mp4",
        pose_estimation_file_path=data_dir_path / "pose_estimation" / f"{video_name}.csv",
        output_dir_path=output_dir_path,
        details_row=row,
        stub_test=stub_test,
    )
