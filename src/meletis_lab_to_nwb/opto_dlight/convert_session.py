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
    output_dir_path: str | Path,
    subject_id: str,
    session_date: datetime.datetime,
    group: str,
    line: str,
    intensity_mw: float,
    frequency_hz: float,
    stub_test: bool = False,
    verbose: bool = True,
):
    """Convert a single opto+dLight session to NWB.

    Parameters
    ----------
    ttl_file_path : str or Path
        Path to the TTL CSV file containing optogenetic stimulation data.
    signal_file_path : str or Path
        Path to the fiber photometry signal CSV file.
    output_dir_path : str or Path
        Path to the directory where the NWB file will be saved.
    subject_id : str
        The subject identifier (mouse ID).
    session_date : datetime.datetime
        The session start time with timezone info.
    group : str
        The recording site / experimental group (e.g., "dStr", "vStr").
    line : str
        The genetic line (e.g., "anxa1-flp").
    intensity_mw : float
        Laser intensity in milliwatts for this session.
    frequency_hz : float
        Laser stimulation frequency in Hz.
    stub_test : bool, optional
        If True, only convert a small amount of data for testing, by default False.
    verbose : bool, optional
        If True, print verbose output, by default True.
    """
    ttl_file_path = Path(ttl_file_path)
    signal_file_path = Path(signal_file_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    video_name = ttl_file_path.stem
    session_id = f"opto_dlight_{group}_{intensity_mw}mW"
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{video_name}.nwb"

    source_data = dict(
        Optogenetics=dict(file_path=str(ttl_file_path)),
        FiberPhotometry=dict(file_path=str(signal_file_path)),
    )
    conversion_options = dict(
        Optogenetics=dict(
            stub_test=stub_test,
            intensity_mw=intensity_mw,
            frequency_hz=frequency_hz,
        ),
        FiberPhotometry=dict(stub_test=stub_test),
    )

    converter = OptoDlightNWBConverter(source_data=source_data, verbose=verbose)

    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = session_date
    metadata["NWBFile"]["session_id"] = session_id

    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["genotype"] = line

    # Override per-session recording location (Allen Atlas names)
    metadata["FiberPhotometry"]["location"] = "Caudoputamen" if group == "dStr" else "Nucleus accumbens"

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
    stub_test = True

    details_file_path = data_dir_path / "details.csv"
    with open(details_file_path) as f:
        reader = csv.DictReader(f)
        row = next(reader)

    video_name = row["video"]
    date_str = video_name.replace("oft_", "")
    session_date = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H_%M_%S").replace(
        tzinfo=ZoneInfo("Europe/Stockholm")
    )

    session_to_nwb(
        ttl_file_path=data_dir_path / "TTL" / f"{video_name}.csv",
        signal_file_path=data_dir_path / "signal" / f"{video_name}_signal_df.csv",
        output_dir_path=output_dir_path,
        subject_id=row["mouse.ID"],
        session_date=session_date,
        group=row["group"],
        line=row["line"],
        intensity_mw=float(row["intenisty"]),
        frequency_hz=float(row["frequency"]),
        stub_test=stub_test,
    )
