"""Primary script to run to convert a single session of open field test data."""

import csv
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.open_field_test import OpenFieldTestNWBConverter

# Per-group overrides for fiber photometry metadata in the oft_fp sub-experiment.
# Keys match the `group` column of details.csv; values populate
# `FiberPhotometry.location`, `FiberPhotometry.indicator_label`, and the human-readable
# `Indicator.description`. Group names mirror the water-consumption convention.
GROUP_FP_CONFIG = {
    # dLight_dStr → dCP, dLight_vStr → cCP confirmed by the lab.
    # fp_dat / fp_anxa1 / dat-cre / anxa1-flp: fiber in dCP to record axonal jGCaMP8m
    # signals from SN→dCP projections (same confirmation as water_consumption).
    "dLight_dStr": dict(
        location="Dorsal caudoputamen",
        fiber_insertion_key="dCP",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
    ),
    "dLight_vStr": dict(
        location="Central caudoputamen",
        fiber_insertion_key="cCP",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
    ),
    "fp_dat": dict(
        location="Dorsal caudoputamen",
        fiber_insertion_key="dCP",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_cpu",
    ),
    "fp_anxa1": dict(
        location="Dorsal caudoputamen",
        fiber_insertion_key="dCP",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_cpu",
    ),
    # OFT-specific group label for pan-DA DAT-Cre mice (same hardware/indicator as fp_dat).
    "dat-cre": dict(
        location="Dorsal caudoputamen",
        fiber_insertion_key="dCP",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_cpu",
    ),
    # OFT-specific group label for Anxa1-Flp mice (same hardware/indicator as fp_anxa1).
    "anxa1-flp": dict(
        location="Dorsal caudoputamen",
        fiber_insertion_key="dCP",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_cpu",
    ),
}


def _parse_session_date(video_name: str) -> datetime.datetime:
    """Parse session datetime from video filename, handling both oft_ and tmaze_ prefixes."""
    if video_name.startswith("oft_"):
        date_str = video_name[4:]
    elif video_name.startswith("tmaze_"):
        date_str = video_name[6:]
    else:
        raise ValueError(f"Unexpected video name prefix: {video_name}")
    return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(tzinfo=ZoneInfo("Europe/Stockholm"))


def _get_sex(aligned_file_path: Path | None) -> str:
    """Extract subject sex from the first row of the aligned CSV, falling back to 'U'."""
    if aligned_file_path is None:
        return "U"
    try:
        with open(aligned_file_path) as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
            if row and "sex" in row:
                sex = row["sex"]
                if isinstance(sex, str) and sex.lower() in ("m", "f"):
                    return sex.upper()
    except Exception:
        pass
    return "U"


def session_to_nwb(
    *,
    video_file_path: str | Path,
    pose_estimation_file_path: str | Path,
    output_dir_path: str | Path,
    details_row: dict,
    vame_157_file_path: str | Path | None = None,
    vame_36_file_path: str | Path | None = None,
    signal_file_path: str | Path | None = None,
    aligned_file_path: str | Path | None = None,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single open field test session to NWB.

    Parameters
    ----------
    video_file_path : str or Path
        Path to the session video file (.mp4).
    pose_estimation_file_path : str or Path
        Path to the DeepLabCut pose estimation output (.csv).
    output_dir_path : str or Path
        Path to the directory where the NWB files will be saved.
    details_row : dict
        A dictionary containing session details from the details.csv file, with
        keys like "mouse.ID", "DoB", "group", "line", and optionally "sex".
    vame_157_file_path : str or Path or None, optional
        Path to VAME 157-motif .npy file, if available.
    vame_36_file_path : str or Path or None, optional
        Path to VAME 36-motif .npy file, if available.
    signal_file_path : str or Path or None, optional
        Path to fiber photometry signal CSV, if available.
    aligned_file_path : str or Path or None, optional
        Path to aligned analysis CSV, if available.
    stub_test : bool, optional
        If True, only convert a small amount of data for testing, by default False.
    verbose : bool, optional
        If True, print verbose output, by default True.
    """
    subject_id = details_row["mouse.ID"].replace("_", "-")

    output_dir_path = Path(output_dir_path) / f"sub-{subject_id}"
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    video_file_path = Path(video_file_path)
    pose_estimation_file_path = Path(pose_estimation_file_path)

    video_name = video_file_path.stem
    session_id = video_name.replace("_", "-")
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    group = details_row["group"]
    line = details_row["line"]
    session_date = _parse_session_date(video_name)
    sex = _get_sex(Path(aligned_file_path) if aligned_file_path is not None else None)

    source_data = dict(
        Video=dict(file_paths=[video_file_path]),
        PoseEstimation=dict(file_path=str(pose_estimation_file_path)),
    )
    conversion_options = dict(
        Video=dict(),
        PoseEstimation=dict(),
    )

    if vame_157_file_path is not None:
        source_data["VAME157"] = dict(file_path=str(vame_157_file_path), name_suffix="157")
        conversion_options["VAME157"] = dict()

    if vame_36_file_path is not None:
        source_data["VAME36"] = dict(file_path=str(vame_36_file_path), name_suffix="36")
        conversion_options["VAME36"] = dict()

    if signal_file_path is not None:
        fiber_photometry_metadata_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        source_data["FiberPhotometry"] = dict(
            file_path=str(signal_file_path), metadata_yaml_path=fiber_photometry_metadata_path
        )
        conversion_options["FiberPhotometry"] = dict()

    if aligned_file_path is not None:
        source_data["Behavior"] = dict(file_path=str(aligned_file_path))
        conversion_options["Behavior"] = dict()

    converter = OpenFieldTestNWBConverter(source_data=source_data, verbose=verbose)

    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = session_date
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    t_zone = ZoneInfo("Europe/Stockholm")
    date_of_birth = datetime.datetime.strptime(details_row["DoB"], "%d-%b-%y").replace(tzinfo=t_zone)
    metadata["Subject"].update(
        subject_id=subject_id,
        sex=sex,
        genotype=line,
        date_of_birth=date_of_birth,
    )

    # --- Per-group fiber photometry overrides (only for oft_fp sessions with FP data) ---
    if signal_file_path is not None:
        fp_config = GROUP_FP_CONFIG.get(group)
        if fp_config is not None:
            metadata["FiberPhotometry"]["location"] = fp_config["location"]
            metadata["FiberPhotometry"]["indicator_label"] = fp_config["indicator_label"]
            metadata["FiberPhotometry"]["OpticalFiber"]["name"] = fp_config["optical_fiber_name"]
            # Inject the correct Indicator entry from the per-group Indicators mapping in
            # fiber_photometry_metadata.yaml (name, manufacturer, description are all set there).
            indicators = metadata["FiberPhotometry"].get("Indicators", {})
            if group in indicators:
                metadata["FiberPhotometry"]["Indicator"] = indicators[group]
        else:
            metadata["FiberPhotometry"]["location"] = "unknown"

        fiber_insertions = metadata["FiberPhotometry"].get("FiberInsertions", {})
        insertion_key = fp_config.get("fiber_insertion_key", group) if fp_config else group
        if insertion_key in fiber_insertions:
            metadata["FiberPhotometry"]["FiberInsertion"] = fiber_insertions[insertion_key]

    # Update camera device from behavior_metadata.yaml
    behavior_metadata_path = Path(__file__).parent / "behavior_metadata.yaml"
    behavior_metadata = load_dict_from_file(behavior_metadata_path)
    video_device = behavior_metadata["VideoDevice"]
    video_key = f"Video {video_name}"
    metadata["Behavior"]["ExternalVideos"][video_key]["device"]["name"] = video_device["name"]
    metadata["Behavior"]["ExternalVideos"][video_key]["device"]["description"] = video_device["description"]
    # Replace the DLC auto-generated camera device with the shared video camera device so
    # both the video and pose estimation reference the same device object in the NWB file.
    metadata["PoseEstimation"]["Devices"].pop("CameraPoseEstimationDeepLabCut", None)
    metadata["PoseEstimation"]["Devices"][video_device["name"]] = {
        "name": video_device["name"],
        "description": video_device["description"],
    }
    for container in metadata["PoseEstimation"]["PoseEstimationContainers"].values():
        container["devices"] = [video_device["name"]]

    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )

    if verbose:
        print(f"Converted {nwbfile_path} successfully.")


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/oft")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/open_field_test")
    stub_test = False

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        # Find a session with fiber photometry signal for a meaningful test run.
        for row in reader:
            if row.get("has_signal_df", "").upper() == "TRUE":
                break

    video_name = row["video"]
    vame_157_path = data_dir_path / "vame_157" / f"47_km_label_{video_name}.npy"
    vame_36_path = data_dir_path / "vame_36" / f"47_km_label_{video_name}.npy"
    signal_path = data_dir_path / "signal" / f"{video_name}_signal_df.csv"
    aligned_path = data_dir_path / "aligned_157" / f"{video_name}_aligned.csv"

    session_to_nwb(
        video_file_path=data_dir_path / "videos" / f"{video_name}.mp4",
        pose_estimation_file_path=data_dir_path / "pose_estimation" / f"{video_name}.csv",
        output_dir_path=output_dir_path,
        details_row=row,
        vame_157_file_path=vame_157_path if vame_157_path.exists() else None,
        vame_36_file_path=vame_36_path if vame_36_path.exists() else None,
        signal_file_path=signal_path if signal_path.exists() else None,
        aligned_file_path=aligned_path if aligned_path.exists() else None,
        stub_test=stub_test,
    )
