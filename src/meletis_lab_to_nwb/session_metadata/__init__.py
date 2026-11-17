"""Session-level condition labels stored as ``lab_meta_data`` in every NWB file."""

from pathlib import Path

from pynwb import NWBFile, get_class, load_namespaces

_NAMESPACE_FILE_PATH = Path(__file__).parent / "spec" / "ndx-meletis-metadata.namespace.yaml"
load_namespaces(str(_NAMESPACE_FILE_PATH))

MeletisSessionMetadata = get_class("MeletisSessionMetadata", "ndx-meletis-metadata")


def add_session_metadata(
    *,
    nwbfile: NWBFile,
    group: str | None = None,
    cohort: str | None = None,
    day: str | None = None,
    light_condition: str | None = None,
) -> None:
    """Add the condition labels of a session to ``nwbfile.lab_meta_data["session_metadata"]``.

    Values are stored as written in the lab's details.csv. Fields that do not apply to a
    conversion are left out.
    """
    fields = dict(group=group, cohort=cohort, day=day, light_condition=light_condition)
    fields = {key: value for key, value in fields.items() if value}
    nwbfile.add_lab_meta_data(MeletisSessionMetadata(name="session_metadata", **fields))


__all__ = ["MeletisSessionMetadata", "add_session_metadata"]
