"""Primary script to run to convert a single session of arrow maze choice task data."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.arrow_maze_choice_task import ArrowMazeChoiceTaskNWBConverter


def session_to_nwb(
    *,
    video_file_path: str | Path,
    pose_estimation_file_path: str | Path,
    output_dir_path: str | Path,
    subject_id: str,
    line: str,
    day: str,
    experiment: str,
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
    subject_id : str
        The subject identifier (mouse ID).
    line : str
        The genetic line (e.g., "WT", "anxa1-flp").
    day : str
        The session day (e.g., "day01").
    experiment : str
        The experiment name (e.g., "tmaze_6ohda", "tmaze_anxa1_tet").
    stub_test : bool, optional
        If True, only convert a small amount of data for testing, by default False.
    verbose : bool, optional
        If True, print verbose output, by default True.
    """
    video_file_path = Path(video_file_path)
    pose_estimation_file_path = Path(pose_estimation_file_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    subject_id = subject_id.replace("_", "-")
    experiment = experiment.replace("_", "-")
    session_id = f"{experiment}-{day}"
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

    metadata = converter.get_metadata()

    session_date = datetime.datetime.strptime(video_file_path.stem, "tmaze_%Y-%m-%dT%H_%M_%S").replace(
        tzinfo=ZoneInfo("Europe/Stockholm")
    )

    metadata["NWBFile"]["session_start_time"] = session_date
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["genotype"] = line

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
        subject_id=row["mouse.ID"],
        line=row["line"],
        day=row["day"],
        experiment=row["experiment"],
        stub_test=stub_test,
    )
