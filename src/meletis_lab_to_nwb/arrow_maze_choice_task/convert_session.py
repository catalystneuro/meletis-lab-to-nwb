"""Primary script to run to convert a single session of arrow maze choice task data."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from neuroconv.datainterfaces.behavior.video.video_utils import get_video_timestamps
from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata
from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.arrow_maze_choice_task import ArrowMazeChoiceTaskNWBConverter
from meletis_lab_to_nwb.session_metadata import add_session_metadata


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

    video_metadata_key = "video"
    pose_estimation_metadata_key = "PoseEstimationDeepLabCut"
    source_data = dict(
        Video=dict(file_paths=[video_file_path], metadata_key=video_metadata_key),
        PoseEstimation=dict(file_path=str(pose_estimation_file_path), metadata_key=pose_estimation_metadata_key),
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

    # Enrich session description with per-session experimental context from details.csv.
    # `day` is the training day (day01–day04); `group` is the treatment group
    # (ctrl, 6ohda, asc.acid, anxa1_tet); `experiment` is the cohort identifier
    # (tmaze_6ohda or tmaze_anxa1_tet).
    day = details_row.get("day", "").lstrip("day").lstrip("0") or "0"
    group = details_row.get("group", "")
    experiment = details_row.get("experiment", "")
    base_description = metadata["NWBFile"]["session_description"]
    metadata["NWBFile"][
        "session_description"
    ] = f"Day {day} from group '{group}' cohort '{experiment}'. {base_description}"

    sex = details_row.get("sex", "u").upper()
    metadata["Subject"].update(
        subject_id=subject_id,
        sex=sex if sex in ("M", "F") else "U",
        genotype=details_row.get("line", ""),
    )
    if details_row["DoB"] in ("NA", ""):
        # The lab has no date of birth for this mouse; use the age range stated in the paper (2-6 months).
        metadata["Subject"]["age"] = "P2M/P6M"
    else:
        date_of_birth = datetime.datetime.strptime(details_row["DoB"], "%d-%b-%y").replace(tzinfo=t_zone)
        metadata["Subject"]["date_of_birth"] = date_of_birth

    # Update camera device from behavior_metadata.yaml
    behavior_metadata_path = Path(__file__).parent / "behavior_metadata.yaml"
    video_device = load_dict_from_file(behavior_metadata_path)["VideoDevice"]
    camera_metadata_key = metadata["Behavior"]["ExternalVideos"][video_metadata_key]["device_metadata_key"]
    metadata["Devices"][camera_metadata_key] = dict(name=video_device["name"], description=video_device["description"])
    # Link the pose estimation to the same camera device as the video.
    pose_estimation_metadata = metadata["Pose"]["PoseEstimations"][pose_estimation_metadata_key]
    pose_estimation_metadata["device_metadata_key"] = camera_metadata_key
    pose_estimation_metadata["description"] = "2D keypoint coordinates estimated using DeepLabCut."

    # Store the session's condition labels as structured metadata, not only in the description.
    nwbfile = make_nwbfile_from_metadata(metadata=metadata)
    add_session_metadata(nwbfile=nwbfile, group=group, cohort=experiment, day=details_row.get("day"))

    converter.run_conversion(
        nwbfile=nwbfile,
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

    # The updated table fills in the sex and date of birth that details.csv lacks for 32 sessions.
    details_file_path = data_dir_path / "details_tmaze_updated.csv"
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
