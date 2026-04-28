"""Primary script to run to convert a single session of open field test data."""

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
    "dLight_dStr": dict(
        location="Caudoputamen",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
    ),
    "dLight_vStr": dict(
        # `vStr` likely corresponds to central caudoputamen (cCP) — see LAB_REVIEW.md Q3.
        location="Caudoputamen",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
    ),
    "fp_dat": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
    ),
    "fp_anxa1": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
    ),
    # OFT-specific group label for pan-DA DAT-Cre mice (same hardware/indicator as fp_dat).
    "dat-cre": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
    ),
    # OFT-specific group label for Anxa1-Flp mice (same hardware/indicator as fp_anxa1).
    "anxa1-flp": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
    ),
}


def session_to_nwb(
    *,
    video_file_path: str | Path,
    pose_estimation_file_path: str | Path,
    output_dir_path: str | Path,
    subject_id: str,
    session_date: datetime.datetime,
    group: str,
    line: str,
    experiment: str,
    vame_157_file_path: str | Path | None = None,
    vame_36_file_path: str | Path | None = None,
    signal_file_path: str | Path | None = None,
    aligned_file_path: str | Path | None = None,
    sex: str = "U",
    ctrl_vs_exp: str | None = None,
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
        Path to the directory where the NWB file will be saved.
    subject_id : str
        The subject identifier (mouse ID).
    session_date : datetime.datetime
        The session start time with timezone info.
    group : str
        The experimental group (e.g., "6OHDA", "ctrl", "Tetx").
    line : str
        The genetic line (e.g., "WT", "Anxa1-flp/DAT-cre").
    experiment : str
        The experiment name (e.g., "oft_6OHDA", "oft_fp").
    vame_157_file_path : str or Path or None, optional
        Path to VAME 157-motif .npy file, if available.
    vame_36_file_path : str or Path or None, optional
        Path to VAME 36-motif .npy file, if available.
    signal_file_path : str or Path or None, optional
        Path to fiber photometry signal CSV, if available.
    aligned_file_path : str or Path or None, optional
        Path to aligned analysis CSV, if available.
    sex : str, optional
        Subject sex ("M", "F", or "U"), by default "U".
    ctrl_vs_exp : str or None, optional
        Control vs experimental group label.
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

    video_name = video_file_path.stem
    session_id = experiment
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{video_name}.nwb"

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

    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["genotype"] = line
    metadata["Subject"]["sex"] = sex.upper() if sex and sex.lower() in ("m", "f") else "U"

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
        if group in fiber_insertions:
            metadata["FiberPhotometry"]["FiberInsertion"] = fiber_insertions[group]

    converter.run_conversion(
        metadata=metadata,
        nwbfile_path=nwbfile_path,
        conversion_options=conversion_options,
        overwrite=True,
    )

    if verbose:
        print(f"Converted {nwbfile_path}")


if __name__ == "__main__":
    import csv

    data_dir_path = Path("/Volumes/T9/data/Meletis/oft")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/open_field_test")
    stub_test = True

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        # Find a session with fiber photometry signal
        for row in reader:
            if row.get("has_signal_df", "").upper() == "TRUE":
                break

    video_name = row["video"]

    # Parse session date from video name (handles both oft_ and tmaze_ prefixes)
    date_str = video_name.split("_", 1)[1] if video_name.startswith("oft_") else video_name.replace("tmaze_", "")
    session_date = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(
        tzinfo=ZoneInfo("Europe/Stockholm")
    )

    # Check for optional data streams
    vame_157_path = data_dir_path / "vame_157" / f"47_km_label_{video_name}.npy"
    vame_36_path = data_dir_path / "vame_36" / f"47_km_label_{video_name}.npy"
    signal_path = data_dir_path / "signal" / f"{video_name}_signal_df.csv"
    aligned_path = data_dir_path / "aligned_157" / f"{video_name}_aligned.csv"

    session_to_nwb(
        video_file_path=data_dir_path / "videos" / f"{video_name}.mp4",
        pose_estimation_file_path=data_dir_path / "pose_estimation" / f"{video_name}.csv",
        output_dir_path=output_dir_path,
        subject_id=row["mouse.ID"],
        session_date=session_date,
        group=row["group"],
        line=row["line"],
        experiment=row["experiment"],
        vame_157_file_path=vame_157_path if vame_157_path.exists() else None,
        vame_36_file_path=vame_36_path if vame_36_path.exists() else None,
        signal_file_path=signal_path if signal_path.exists() else None,
        aligned_file_path=aligned_path if aligned_path.exists() else None,
        sex="U",
        ctrl_vs_exp=row.get("ctrl.vs.exp"),
        stub_test=stub_test,
    )
