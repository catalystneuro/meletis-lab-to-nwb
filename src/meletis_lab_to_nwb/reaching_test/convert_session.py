"""Primary script to run to convert a single session of the reaching test."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.reaching_test import ReachingTestNWBConverter

# Per-group description of the experimental manipulation. Used to enrich the session
# description so consumers understand the cohort's condition without re-consulting
# details.csv. Keys match the ``group`` column of details.csv.
GROUP_DESCRIPTIONS = {
    "tet": (
        "Anxa1+ SNc dopamine neurons chronically silenced via Flp-dependent tetanus toxin light "
        "chain in Anxa1-Flp mice (tet cohort). Virus: AAV9-hSyn1-chl-dFRT-EGFP_2A_Flag_TeTxLC"
        "(rev)-dFRT (VVF Zurich), 300 nL bilateral SNc injection."
    ),
    "ctrl": ("Littermate control for the tetanus-toxin cohort (no TetTox expression; Anxa1-Flp line)."),
    "arch_anxa1": (
        "Anxa1+ SNc dopamine neurons optogenetically silenced with Archaerhodopsin (Anxa1-Flp, "
        "Arch cohort). Virus: AAV8-nEF-Coff/Fon-Arch3.3-p2a-eYFP (Addgene #137150), 300 nL "
        "bilateral SNc injection."
    ),
    "arch_ctrl": ("Littermate control for the Archaerhodopsin cohort (no Arch expression; Anxa1-Flp line)."),
}

# Friendly labels for the ``light`` column (Arch cohort only).
LIGHT_DESCRIPTIONS = {
    "on": "Optogenetic silencing laser on for the entire session.",
    "on_after_first_reach": (
        "Optogenetic silencing laser activated immediately after the mouse's first reach attempt "
        "of the session. Laser onset was triggered manually by the experimenter."
    ),
    "off": "Optogenetic silencing laser off for the entire session.",
    "-": "Not applicable (non-optogenetic cohort).",
}


def _parse_session_datetime(video_stem: str, tz: ZoneInfo) -> datetime.datetime:
    """Parse session datetime from a video stem like ``reaching_test_2024-04-16T11_06_09``."""
    date_str = video_stem.replace("reaching_test_", "")
    return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(tzinfo=tz)


def session_to_nwb(
    *,
    video_file_path: str | Path,
    pose_estimation_file_path: str | Path,
    behavior_file_path: str | Path | None,
    output_dir_path: str | Path,
    details_row: dict,
    video_frame_rate_hz: float = 60.0,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single reaching-test session to NWB.

    Parameters
    ----------
    video_file_path : str or Path
        Path to the lateral behavior video (``*.avi``). Added by external reference.
    pose_estimation_file_path : str or Path
        Path to the DeepLabCut pose-estimation CSV
        (``*DLC_resnet50_reaching_trainJun9shuffle1_100000.csv``).
    behavior_file_path : str or Path or None
        Path to the manual-annotation CSV (``*_behavior.csv``). Pass ``None`` for
        sessions in which the mouse did not perform any reach attempts (``has_behavior``
        is FALSE in details.csv).
    output_dir_path : str or Path
        Directory for the output NWB file. A ``sub-<subject_id>/`` subdirectory is
        created automatically.
    details_row : dict
        One row from ``details.csv``, providing ``mouse.ID``, ``DoB``, ``group``,
        ``line``, ``sex``, ``phase``, ``light``, ``experiment``, and ``video``.
    video_frame_rate_hz : float, optional
        Video frame rate used to convert reach-annotation frames to seconds. Defaults
        to 60 Hz (the FLIR camera used for the reaching test).
    stub_test : bool, optional
        If True, convert only a small amount of data. Default False.
    verbose : bool, optional
        Verbose output. Default True.
    """
    video_file_path = Path(video_file_path)
    pose_estimation_file_path = Path(pose_estimation_file_path)
    subject_id = str(details_row["mouse.ID"]).replace("_", "-")

    output_dir_path = Path(output_dir_path) / f"sub-{subject_id}"
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    video_stem = details_row.get("video") or video_file_path.stem
    session_id = video_stem.replace("_", "-")
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    # --- Assemble source_data ---
    source_data = dict(
        Video=dict(file_paths=[str(video_file_path)], video_name="BehaviorVideo"),
        PoseEstimation=dict(
            file_path=str(pose_estimation_file_path),
            subject_name=subject_id,
        ),
    )
    conversion_options = dict(
        Video=dict(),
        PoseEstimation=dict(),
    )
    if behavior_file_path is not None:
        behavior_metadata_yaml_path = Path(__file__).parent / "behavior_metadata.yaml"
        source_data["Behavior"] = dict(
            file_path=str(behavior_file_path),
            video_file_path=str(video_file_path),
            metadata_yaml_path=behavior_metadata_yaml_path,
        )
        conversion_options["Behavior"] = dict(stub_test=stub_test)

    converter = ReachingTestNWBConverter(source_data=source_data, verbose=verbose)

    # --- Metadata assembly ---
    tz = ZoneInfo("Europe/Stockholm")
    session_date = _parse_session_datetime(video_stem, tz)

    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = session_date
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    pose_metadata_path = Path(__file__).parent / "pose_estimation_metadata.yaml"
    if pose_metadata_path.exists():
        metadata = dict_deep_update(metadata, load_dict_from_file(pose_metadata_path))

    # --- Enrich the session description with cohort/phase/light context ---
    group = details_row.get("group", "").strip()
    phase = details_row.get("phase", "").strip()
    light = details_row.get("light", "").strip()
    experiment = details_row.get("experiment", "").strip()
    group_note = GROUP_DESCRIPTIONS.get(group, f"Cohort: {group or 'unknown'}.")
    light_note = LIGHT_DESCRIPTIONS.get(light, f"Light condition: {light or 'unknown'}.")
    phase_note = f"Test phase: {phase or 'unknown'} (sessions run across multiple days per mouse)."
    base_session_description = metadata["NWBFile"].get("session_description", "").strip()
    metadata["NWBFile"]["session_description"] = (
        f"{base_session_description}\n\n"
        f"Experiment: {experiment or 'reaching_test'}. {group_note} {phase_note} {light_note}"
    ).strip()

    # --- Subject metadata ---
    dob_raw = details_row.get("DoB", "").strip()
    date_of_birth = None
    if dob_raw:
        try:
            date_of_birth = datetime.datetime.strptime(dob_raw, "%d-%b-%y").replace(tzinfo=tz)
        except ValueError:
            date_of_birth = None

    sex_raw = (details_row.get("sex") or "u").strip().upper()
    sex = sex_raw if sex_raw in ("M", "F") else "U"

    subject_updates = dict(
        subject_id=subject_id,
        sex=sex,
        genotype=(details_row.get("line") or "").strip().capitalize() or "Unknown",
    )
    if date_of_birth is not None:
        subject_updates["date_of_birth"] = date_of_birth
    metadata["Subject"].update(subject_updates)

    # Update camera device from behavior_metadata.yaml
    behavior_metadata_yaml_path = Path(__file__).parent / "behavior_metadata.yaml"
    video_device = load_dict_from_file(behavior_metadata_yaml_path)["VideoDevice"]
    metadata["Behavior"]["ExternalVideos"]["BehaviorVideo"]["device"]["name"] = video_device["name"]
    metadata["Behavior"]["ExternalVideos"]["BehaviorVideo"]["device"]["description"] = video_device["description"]

    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )

    if verbose:
        print(f"Converted {nwbfile_path} successfully.")

    return nwbfile_path


if __name__ == "__main__":
    import csv

    data_dir_path = Path("/Volumes/T9/data/Meletis/reaching_test")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/reaching_test")
    stub_test = False

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        # Pick the first row that has both DLC and manual behavior annotations for a
        # demo that exercises every interface.
        for row in reader:
            if row.get("has_behavior", "").upper() == "TRUE" and row.get("has_dlc", "").upper() == "TRUE":
                break
        else:
            raise RuntimeError("No reaching_test session with both behavior and DLC was found in details.csv")

    video_stem = row["video"]
    video_file_path = data_dir_path / "videos" / f"{video_stem}.avi"
    pose_estimation_file_path = (
        data_dir_path / "pose_estimation" / f"{video_stem}DLC_resnet50_reaching_trainJun9shuffle1_100000.csv"
    )
    behavior_file_path = data_dir_path / "annotations" / f"{video_stem}_behavior.csv"

    session_to_nwb(
        video_file_path=video_file_path,
        pose_estimation_file_path=pose_estimation_file_path,
        behavior_file_path=behavior_file_path if behavior_file_path.exists() else None,
        output_dir_path=output_dir_path,
        details_row=row,
        stub_test=stub_test,
    )
