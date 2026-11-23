"""HERD references from the ``external_resources.yaml`` of a sub-conversion (from the nwb-convert skill).

Each sub-conversion folder has an ``external_resources.yaml`` that links values written in the files
(species, strain, institution, experimenters, brain-region ``location`` values and pose-estimation body
parts) to terms in external ontologies and registries. The references are stored in the NWB file under
``/general/external_resources`` and read back with ``nwbfile.external_resources.to_dataframe()``.
"""

from hdmf.common import DynamicTable
from pynwb import NWBFile
from pynwb.resources import HERD


def add_external_resources(nwbfile: NWBFile, terms: dict) -> None:
    """Write the terms in external_resources.yaml into the file as HERD references.

    Parameters
    ----------
    nwbfile : NWBFile
        The file, after the interfaces have added their data and before it is written.
    terms : dict
        The content of ``external_resources.yaml``: for each kind of value (``species``, ``strain``,
        ``institution``, ``experimenter``, ``brain_regions``, ``body_parts``), the value as written in
        the file mapped to one term ``{id, uri}`` or a list of terms. A value without a term is skipped.
    """
    herd = nwbfile.external_resources
    is_new_herd = herd is None
    if is_new_herd:
        herd = HERD()
    elif nwbfile.get_read_io() is not None:
        return  # references already stored on disk cannot be extended

    def annotate(container, kind, value, attribute=None):
        found = (terms.get(kind) or {}).get(value) or []
        key = value
        for term in found if isinstance(found, list) else [found]:
            herd.add_ref(
                container=container, attribute=attribute, key=key, entity_id=term["id"], entity_uri=term["uri"]
            )
            if isinstance(key, str):
                # Several terms for one value share one key; a second string key would duplicate the references.
                key = herd.get_key(key_name=value)
                key = key[-1] if isinstance(key, list) else key

    # Scalar fields of the file and the subject
    if nwbfile.institution:
        annotate(nwbfile, "institution", nwbfile.institution, attribute="institution")
    for experimenter in nwbfile.experimenter or []:
        annotate(nwbfile, "experimenter", experimenter, attribute="experimenter")
    if nwbfile.subject is not None:
        for field in ("species", "strain"):
            if getattr(nwbfile.subject, field, None):
                annotate(nwbfile.subject, field, getattr(nwbfile.subject, field), attribute=field)

    # Every anatomical `location` (table columns and scalar attributes) and every ndx-pose body part
    for neurodata_object in nwbfile.all_children():
        if isinstance(neurodata_object, DynamicTable) and "location" in neurodata_object.colnames:
            column = neurodata_object["location"]
            for value in dict.fromkeys(column.data):
                annotate(column, "brain_regions", value)
        elif type(neurodata_object).__name__ == "Skeleton":
            for value in dict.fromkeys(neurodata_object.nodes):
                annotate(neurodata_object, "body_parts", value, attribute="nodes")
        elif isinstance(getattr(neurodata_object, "location", None), str):
            annotate(neurodata_object, "brain_regions", neurodata_object.location, attribute="location")

    if is_new_herd and len(herd.keys) > 0:
        nwbfile.external_resources = herd
