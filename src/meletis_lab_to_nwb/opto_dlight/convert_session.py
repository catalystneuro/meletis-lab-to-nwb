"""Primary script to run to convert a single session of opto+dLight data."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neuroconv.utils import dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.opto_dlight import OptoDlightNWBConverter


def session_to_nwb(
    *,
    ttl_file_path: str | Path,
    signal_file_path: str | Path,
    raw_signal_file_path: str | Path | None = None,
    output_dir_path: str | Path,
    details_row: dict | None = None,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single opto+dLight session to NWB.

    Parameters
    ----------
    ttl_file_path : str or Path
        Path to the TTL CSV file containing optogenetic stimulation data.
    signal_file_path : str or Path
        Path to the processed dF/F fiber photometry CSV file (*_signal_df.csv).
    raw_signal_file_path : str or Path, optional
        Path to the raw acquisition fiber photometry CSV file (*_signal.csv) with
        columns ``time``, ``ref`` (405 nm), and ``sig`` (470 nm). When provided,
        raw fluorescence traces are stored in nwbfile.acquisition.
    output_dir_path : str or Path
        Path to the directory where the NWB file will be saved.
    details_row : dict
        A dictionary containing session details from the details.csv file, with
        keys like "mouse.ID", "DoB", "group", "line", "intenisty", and "frequency".
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

    ttl_file_path = Path(ttl_file_path)
    signal_file_path = Path(signal_file_path)
    video_name = ttl_file_path.stem

    session_id = video_name.replace("_", "-")
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    fp_source = dict(file_path=str(signal_file_path))
    if raw_signal_file_path is not None:
        fp_source["raw_file_path"] = str(raw_signal_file_path)

    source_data = dict(
        Optogenetics=dict(file_path=str(ttl_file_path)),
        FiberPhotometry=fp_source,
    )
    frequency_hz = float(details_row["frequency"])
    start_fp = float(details_row.get("start.fp", 0.0))
    intensity_mw = float(details_row["intenisty"])
    conversion_options = dict(
        Optogenetics=dict(
            stub_test=stub_test,
            intensity_mw=intensity_mw,
            frequency_hz=frequency_hz,
            start_fp=start_fp,
        ),
        FiberPhotometry=dict(stub_test=stub_test),
    )

    converter = OptoDlightNWBConverter(source_data=source_data, verbose=verbose)

    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"]
    t_zone = ZoneInfo("Europe/Stockholm")
    session_start_time.replace(tzinfo=t_zone)
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    # Select the correct viral vector and FP indicator based on mouse line.
    # Anxa1-Flp → AAV8-nEF-Coff/Fon-ChRmine-oScarlet  (Addgene #137160, Flp-dependent).
    # DAT-Cre   → AAV8-nEF-Con/Foff 2.0-ChRmine-oScarlet (Addgene #137161, Cre-dependent).
    # Both lines use the same dLight1.3b sensor; descriptions reference the correct neuron population.
    mouse_line = details_row.get("line", "").lower().strip()

    viral_vectors = metadata["Optogenetics"].get("ViralVectors", {})
    if mouse_line not in viral_vectors:
        raise ValueError(
            f"Unknown mouse line '{mouse_line}' — no ViralVector entry in optogenetics_metadata.yaml. "
            f"Known lines: {list(viral_vectors.keys())}"
        )
    metadata["Optogenetics"]["ViralVector"] = viral_vectors[mouse_line]

    indicators = metadata["FiberPhotometry"].get("Indicators", {})
    if mouse_line not in indicators:
        raise ValueError(
            f"Unknown mouse line '{mouse_line}' — no Indicator entry in fiber_photometry_metadata.yaml. "
            f"Known lines: {list(indicators.keys())}"
        )
    metadata["FiberPhotometry"]["Indicator"] = indicators[mouse_line]

    date_of_birth = datetime.datetime.strptime(details_row["DoB"], "%d-%b-%y").replace(tzinfo=t_zone)
    metadata["Subject"].update(
        subject_id=subject_id,
        sex=details_row.get("sex", "u").upper(),
        genotype=details_row.get("line", "").capitalize(),
        date_of_birth=date_of_birth,
    )

    # Override per-session recording location (Allen Atlas names) and fiber insertion coordinates.
    group = details_row["group"]
    group_names_to_locations = {
        "dStr": "Dorsal caudoputamen",
        "vStr": "Central caudoputamen",
    }
    metadata["FiberPhotometry"]["location"] = group_names_to_locations.get(group, "unknown")

    fiber_insertions = metadata["FiberPhotometry"].get("FiberInsertions", {})
    if group not in fiber_insertions:
        raise ValueError(
            f"Unknown group '{group}' — no FiberInsertion entry in fiber_photometry_metadata.yaml. "
            f"Known groups: {list(fiber_insertions.keys())}"
        )
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

    data_dir_path = Path("/Volumes/T9/data/Meletis/opto+dLight")
    output_dir_path = Path("/Users/weian/catalystneuro/meletis-lab-to-nwb/nwb_output/opto_dlight")
    stub_test = False

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)

    video_name = row["video"]

    session_to_nwb(
        ttl_file_path=data_dir_path / "TTL" / f"{video_name}.csv",
        signal_file_path=data_dir_path / "signal" / f"{video_name}_signal_df.csv",
        raw_signal_file_path=data_dir_path / "signal" / f"{video_name}_signal.csv",
        output_dir_path=output_dir_path,
        details_row=row,
        stub_test=stub_test,
    )
