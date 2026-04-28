"""Primary script to run to convert a single session of the water-consumption reaching task."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.water_consumption import WaterConsumptionNWBConverter

# Per-group overrides for fiber photometry metadata. Keys match the `group` column of
# details.csv; values populate `FiberPhotometry.location`, `FiberPhotometry.indicator_label`,
# and the human-readable `Indicator.description`. Flagged in open_questions.md where the
# manuscript text is ambiguous (in particular, the exact GCaMP variant for fp_dat/fp_anxa1,
# and whether `dLight_vStr` is cCP or NAc).
GROUP_FP_CONFIG = {
    "dLight_dStr": dict(
        location="Caudoputamen",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
        indicator_description=(
            "Genetically encoded dopamine indicator dLight1.3b delivered via unilateral "
            "AAV5-CAG-dLight1.3b (Addgene #125560) injection into the dorsal caudoputamen "
            "(dCP; Mantas et al. 2026, lines 628-629 and 656-658)."
        ),
    ),
    "dLight_vStr": dict(
        # Manuscript describes dCP and cCP (both in Caudoputamen); see open_questions.md
        # item 2 carried over from the opto+dLight conversion — the `vStr` label may be a
        # lab-internal shorthand for cCP rather than nucleus accumbens.
        location="Caudoputamen",
        indicator_label="dLight1.3b",
        optical_fiber_name="optical_fiber_cpu",
        indicator_description=(
            "Genetically encoded dopamine indicator dLight1.3b delivered via unilateral "
            "AAV5-CAG-dLight1.3b (Addgene #125560) injection into the central caudoputamen "
            "(cCP; assuming `vStr` in details.csv corresponds to the manuscript's cCP target — "
            "see open_questions.md)."
        ),
    ),
    "fp_dat": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
        indicator_name="jGCaMP8m",
        indicator_manufacturer="Addgene",
        indicator_description=(
            "Genetically encoded calcium indicator jGCaMP8m expressed pan-DA in SN dopamine "
            "neurons via a Cre-dependent AAV in DAT-Cre mice. Delivered as 300 nL unilateral "
            "injection of pGP-AAV9-CAG-FLEX-jGCaMP8m-WPRE (Addgene #162381) into the SN "
            "compact part."
        ),
    ),
    "fp_anxa1": dict(
        location="Substantia nigra, compact part",
        indicator_label="jGCaMP8m",
        optical_fiber_name="optical_fiber_snc",
        indicator_name="jGCaMP8m",
        indicator_manufacturer="VVF Zurich",
        indicator_description=(
            "Genetically encoded calcium indicator jGCaMP8m selectively expressed in Anxa1+ "
            "SN dopamine neurons via a Flp-dependent AAV in Anxa1-Flp mice. Delivered as "
            "300–500 nL unilateral injection of AAV-DJ/2-hSyn1-chl-dFRT-jGCaMP8m(rev)-dFRT-"
            "WPRE-bGHp (VVF Zurich) into the SN compact part."
        ),
    ),
}


def session_to_nwb(
    *,
    signal_file_path: str | Path,
    raw_signal_file_path: str | Path | None,
    behavior_file_path: str | Path,
    video_file_path: str | Path,
    output_dir_path: str | Path,
    details_row: dict,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single water-consumption reaching session to NWB.

    Parameters
    ----------
    signal_file_path : str or Path
        Path to the processed dF/F fiber photometry CSV (``*_signal_df.csv``).
    raw_signal_file_path : str or Path or None
        Path to the raw acquisition fiber photometry CSV (``*_signal.csv``) with
        columns ``time``, ``ref``, ``sig``. Optional.
    behavior_file_path : str or Path
        Path to the behavior annotation CSV (``*_behavior.csv``).
    video_file_path : str or Path
        Path to the lateral behavior video (``*.avi``). When provided, the video is added
        as an ExternalVideoInterface (not copied into the NWB file).
    output_dir_path : str or Path
        Directory for the output NWB file. A ``sub-<subject_id>/`` subdirectory is created.
    details_row : dict
        One row from ``details.csv``, providing ``mouse.ID``, ``DoB``, ``group``, ``line``,
        ``sex``, and ``video`` (the session stem).
    stub_test : bool, optional
        If True, convert only a small amount of data. Default False.
    verbose : bool, optional
        Verbose output. Default True.
    """
    subject_id = details_row["mouse.ID"].replace("_", "-")
    output_dir_path = Path(output_dir_path) / f"sub-{subject_id}"
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    signal_file_path = Path(signal_file_path)
    behavior_file_path = Path(behavior_file_path)
    video_stem = details_row["video"]  # e.g. reaching_test_2024-04-23T10_04_21
    session_id = video_stem.replace("_", "-")
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    # --- Assemble source_data ---
    fp_source = dict(
        file_path=str(signal_file_path),
        metadata_yaml_path=Path(__file__).parent / "fiber_photometry_metadata.yaml",
    )
    if raw_signal_file_path is not None:
        fp_source["raw_file_path"] = str(raw_signal_file_path)

    behavior_metadata_yaml_path = Path(__file__).parent / "behavior_metadata.yaml"
    source_data = dict(
        FiberPhotometry=fp_source,
        Behavior=dict(
            file_path=behavior_file_path,
            video_file_path=video_file_path,
            metadata_yaml_path=behavior_metadata_yaml_path,
        ),
        Video=dict(file_paths=[str(video_file_path)], video_name="BehaviorVideo"),
    )
    conversion_options = dict(
        FiberPhotometry=dict(stub_test=stub_test),
        Behavior=dict(stub_test=stub_test),
    )

    converter = WaterConsumptionNWBConverter(source_data=source_data, verbose=verbose)

    # --- Metadata assembly ---
    t_zone = ZoneInfo("Europe/Stockholm")
    date_str = video_stem.replace("reaching_test_", "")
    session_date = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(tzinfo=t_zone)

    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = session_date
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    date_of_birth = datetime.datetime.strptime(details_row["DoB"], "%d-%b-%y").replace(tzinfo=t_zone)
    metadata["Subject"].update(
        subject_id=subject_id,
        sex=details_row.get("sex", "u").upper(),
        genotype=details_row.get("line", "").capitalize(),
        date_of_birth=date_of_birth,
    )

    # --- Per-group fiber photometry overrides (indicator + location + fiber insertion) ---
    group = details_row.get("group", "")
    fp_config = GROUP_FP_CONFIG.get(group)
    if fp_config is not None:
        metadata["FiberPhotometry"]["location"] = fp_config["location"]
        metadata["FiberPhotometry"]["indicator_label"] = fp_config["indicator_label"]
        metadata["FiberPhotometry"]["OpticalFiber"]["name"] = fp_config["optical_fiber_name"]
        ind = metadata["FiberPhotometry"]["Indicator"]
        ind["description"] = fp_config["indicator_description"]
        if "indicator_name" in fp_config:
            ind["name"] = fp_config["indicator_name"]
        if "indicator_manufacturer" in fp_config:
            ind["manufacturer"] = fp_config["indicator_manufacturer"]
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
        print(f"Converted {nwbfile_path} successfully.")


if __name__ == "__main__":
    import csv

    data_dir_path = Path("/Volumes/T9/data/Meletis/water_consumption")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/water_consumption")
    stub_test = False

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)

    video_stem = row["video"]
    signal_file_path = data_dir_path / "signal_df" / f"{video_stem}_signal_df.csv"
    raw_signal_file_path = data_dir_path / "signal" / f"{video_stem}_signal.csv"
    behavior_file_path = data_dir_path / "annotations" / f"{video_stem}_behavior.csv"
    video_file_path = data_dir_path / "videos" / f"{video_stem}.avi"

    session_to_nwb(
        signal_file_path=signal_file_path,
        raw_signal_file_path=raw_signal_file_path if raw_signal_file_path.exists() else None,
        behavior_file_path=behavior_file_path,
        video_file_path=video_file_path if video_file_path.exists() else None,
        output_dir_path=output_dir_path,
        details_row=row,
        stub_test=stub_test,
    )
