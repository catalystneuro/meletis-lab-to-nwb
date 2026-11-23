"""Tests for the HERD references and the value meanings (with HED). They use small made-up files and tables."""

import datetime
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import ndx_hed  # noqa: F401  (imported before files are read, so that their HED objects are read as ndx-hed classes)
import numpy as np
import pytest
from hed.errors import ErrorHandler, get_printable_issue_string
from ndx_hed.utils.hed_nwb_validator import HedNWBValidator
from ndx_pose import Skeleton, Skeletons
from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile
from neuroconv.utils import load_dict_from_file
from pynwb import NWBHDF5IO, NWBFile
from pynwb.event import EventsTable
from pynwb.file import Subject

import meletis_lab_to_nwb.interfaces.behaviorinterface as behaviorinterface
from meletis_lab_to_nwb.external_resources import add_external_resources
from meletis_lab_to_nwb.genotype import WILD_TYPE_STRAIN, get_strain
from meletis_lab_to_nwb.interfaces import ReachingBehaviorInterface
from meletis_lab_to_nwb.value_meanings import add_value_meanings

PACKAGE_PATH = Path(__file__).parent.parent / "src" / "meletis_lab_to_nwb"
SUB_CONVERSION_NAMES = [
    "arrow_maze_choice_task",
    "open_field_test",
    "opto_dlight",
    "reaching_test",
    "water_consumption",
]
SUB_CONVERSIONS_WITH_MEANINGS = ["opto_dlight", "reaching_test", "water_consumption"]

# The DeepLabCut keypoints of each sub-conversion (conversion_notes.md and pose_estimation_metadata.yaml)
SKELETON_NODES = {
    "arrow_maze_choice_task": [
        "snout",
        "head",
        "leftFrontPaw",
        "rightFrontPaw",
        "leftBackPaw",
        "rightBackPaw",
        "body",
        "tailBase",
    ],
    "open_field_test": ["snout", "leftFrontPaw", "rightFrontPaw", "leftBackPaw", "rightBackPaw", "tailBase"],
    "reaching_test": ["snout", "tongue", "palm", "wrist", "elbow", "mouth", "spout", "extra"],
}
URI_PREFIXES = {
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "UBERON": "http://purl.obolibrary.org/obo/UBERON_",
    "MBA": "http://purl.obolibrary.org/obo/MBA_",
    "ROR": "https://ror.org/",
    "ORCID": "https://orcid.org/",
    "RRID": "https://scicrunch.org/resolver/RRID:",
}


def _load_terms(sub_conversion_name: str) -> dict:
    return load_dict_from_file(PACKAGE_PATH / sub_conversion_name / "external_resources.yaml")


def _load_annotations(sub_conversion_name: str) -> dict:
    return load_dict_from_file(PACKAGE_PATH / sub_conversion_name / "value_meanings.yaml")


def _make_nwbfile(sub_conversion_name: str, genotype: str) -> NWBFile:
    """A file with the session-level metadata of a sub-conversion, as convert_session.py builds it."""
    metadata = load_dict_from_file(PACKAGE_PATH / sub_conversion_name / "metadata.yaml")
    nwbfile = NWBFile(
        session_description="A made-up session.",
        identifier="made-up",
        session_start_time=datetime.datetime(2024, 3, 1, 10, 0, tzinfo=ZoneInfo("Europe/Stockholm")),
        institution=metadata["NWBFile"]["institution"],
        experimenter=metadata["NWBFile"]["experimenter"],
    )
    nwbfile.subject = Subject(
        subject_id="700001",
        species=metadata["Subject"]["species"],
        strain=get_strain(genotype, metadata["Subject"]["strain"]),
        genotype=genotype,
        sex="M",
        age="P90D",
    )
    return nwbfile


def _write_and_read_references(nwbfile: NWBFile, nwbfile_path: Path):
    """Write the file, read it back and return the HERD references with the name of each annotated object."""
    with NWBHDF5IO(nwbfile_path, "w") as io:
        io.write(nwbfile)
    with NWBHDF5IO(nwbfile_path, "r") as io:
        read_nwbfile = io.read()
        names = {}
        for neurodata_object in read_nwbfile.all_children():
            parent = neurodata_object.parent
            names[neurodata_object.object_id] = (
                neurodata_object.name if parent is None else f"{parent.name}/{neurodata_object.name}"
            )
        references = read_nwbfile.external_resources.to_dataframe()
    references["object"] = references["object_id"].map(names)
    return references


def _reference_set(references) -> set[tuple]:
    return set(zip(references["object"], references["relative_path"], references["key"], references["entity_id"]))


@pytest.mark.parametrize("sub_conversion_name", SUB_CONVERSION_NAMES)
def test_terms_are_well_formed(sub_conversion_name):
    terms = _load_terms(sub_conversion_name)
    assert set(terms) <= {"species", "strain", "institution", "experimenter", "brain_regions", "body_parts"}
    for kind, values in terms.items():
        for value, found in values.items():
            for term in found if isinstance(found, list) else [found]:
                prefix, identifier = term["id"].split(":", 1)
                assert term["uri"] == URI_PREFIXES[prefix] + identifier, (kind, value)
                if prefix == "MBA":
                    assert identifier.isdigit()


@pytest.mark.parametrize("sub_conversion_name", SUB_CONVERSION_NAMES)
def test_every_converter_writes_the_annotations(sub_conversion_name):
    converter_text = (PACKAGE_PATH / sub_conversion_name / "nwbconverter.py").read_text()
    assert "add_external_resources(nwbfile=nwbfile, terms=terms)" in converter_text
    has_meanings = (PACKAGE_PATH / sub_conversion_name / "value_meanings.yaml").exists()
    assert has_meanings == (sub_conversion_name in SUB_CONVERSIONS_WITH_MEANINGS)
    assert ("add_value_meanings(nwbfile=nwbfile, annotations=annotations)" in converter_text) == has_meanings

    convert_session_text = (PACKAGE_PATH / sub_conversion_name / "convert_session.py").read_text()
    assert 'metadata["Subject"]["strain"] = get_strain(metadata["Subject"]["genotype"]' in convert_session_text


def test_get_strain():
    assert get_strain("WT", "C57BL/6N") == WILD_TYPE_STRAIN == "C57BL/6NCrl"
    for genotype in ["Anxa1-Flp", "DAT-Cre", "DAT-Cre/Tfam", "Anxa1-Flp/DAT-Cre", ""]:
        assert get_strain(genotype, "C57BL/6N") == "C57BL/6N"


@pytest.mark.parametrize("sub_conversion_name", SUB_CONVERSION_NAMES)
def test_session_terms_resolve_to_their_objects(sub_conversion_name, tmp_path):
    nwbfile = _make_nwbfile(sub_conversion_name, genotype="WT")
    add_external_resources(nwbfile=nwbfile, terms=_load_terms(sub_conversion_name))
    references = _reference_set(_write_and_read_references(nwbfile, tmp_path / "session.nwb"))

    assert ("root", "general/institution", "Karolinska Institutet", "ROR:056d84691") in references
    assert ("root", "general/experimenter", "Mantas, Ioannis", "ORCID:0000-0001-6288-5439") in references
    assert ("root", "general/experimenter", "Contestabile, Alessandro", "ORCID:0000-0001-6528-1403") in references
    assert ("root", "general/experimenter", "Skara, Vasiliki", "ORCID:0000-0002-0017-6116") in references
    assert ("root/subject", "species", "Mus musculus", "NCBITaxon:10090") in references
    # The wild-type subject resolves to the Charles River C57BL/6NCrl stock
    assert ("root/subject", "strain", "C57BL/6NCrl", "RRID:IMSR_CRL:027") in references


@pytest.mark.parametrize("genotype", ["Anxa1-Flp", "DAT-Cre", "DAT-Cre/Tfam"])
def test_transgenic_subjects_have_no_strain_term(genotype, tmp_path):
    nwbfile = _make_nwbfile("open_field_test", genotype=genotype)
    assert nwbfile.subject.strain == "C57BL/6N"
    add_external_resources(nwbfile=nwbfile, terms=_load_terms("open_field_test"))
    references = _write_and_read_references(nwbfile, tmp_path / "session.nwb")

    assert "strain" not in set(references["relative_path"])
    assert "genotype" not in set(references["relative_path"])
    assert "RRID:IMSR_CRL:027" not in set(references["entity_id"])


@pytest.mark.parametrize("sub_conversion_name", list(SKELETON_NODES))
def test_body_parts_resolve_to_the_skeleton(sub_conversion_name, tmp_path):
    nwbfile = _make_nwbfile(sub_conversion_name, genotype="WT")
    nodes = SKELETON_NODES[sub_conversion_name]
    skeleton = Skeleton(name="Skeleton", nodes=nodes, edges=np.array([[0, 1]], dtype="uint8"))
    behavior_module = nwbfile.create_processing_module(name="behavior", description="Made-up behavior.")
    behavior_module.add(Skeletons(skeletons=[skeleton]))

    terms = _load_terms(sub_conversion_name)
    add_external_resources(nwbfile=nwbfile, terms=terms)
    references = _write_and_read_references(nwbfile, tmp_path / "session.nwb")
    skeleton_references = references[references["object"] == "Skeletons/Skeleton"]

    expected = {(node, terms["body_parts"][node]["id"]) for node in nodes if node in terms["body_parts"]}
    assert set(zip(skeleton_references["key"], skeleton_references["entity_id"])) == expected
    assert set(skeleton_references["relative_path"]) == {"nodes"}
    # Every term in the YAML is used by the skeleton, and the nodes that are not anatomy have none
    assert set(terms["body_parts"]) <= set(nodes)
    assert not {"spout", "extra", "body", "tailBase"} & set(skeleton_references["key"])


# Reads the meanings and validates the HED of a written file in a fresh Python process that imports only ndx-hed.
# The Python class of ndx-optogenetics 0.4.0 (OptogeneticEpochsTable) does not accept `meanings_tables`, so a
# process that has imported it reads the table without its MeaningsTable. The table is in the file and valid,
# and a reader that does not import ndx_optogenetics (PyNWB with the classes generated from the cached schema,
# MatNWB, h5py) sees it.
READ_MEANINGS_SCRIPT = """
import json, sys
import numpy as np
from hdmf.common import MeaningsTable
from hed.errors import ErrorHandler, get_printable_issue_string
from ndx_hed.utils.hed_nwb_validator import HedNWBValidator
from pynwb import NWBHDF5IO

assert "ndx_optogenetics" not in sys.modules
result = dict(tables=[], hed_issues="")
with NWBHDF5IO(sys.argv[1], "r") as io:
    nwbfile = io.read()
    for meanings_table in nwbfile.all_children():
        if isinstance(meanings_table, MeaningsTable):
            result["tables"].append(dict(
                table=meanings_table.parent.name,
                column=meanings_table.target.name,
                values=meanings_table["value"].data[:].tolist(),
                meanings=meanings_table["meaning"].data[:].tolist(),
                hed=(
                    [str(hed) for hed in meanings_table["HED"].data[:]]
                    if "HED" in meanings_table.colnames
                    else [""] * len(meanings_table)
                ),
                in_file=sorted(set(np.asarray(meanings_table.target.data[:]).tolist())),
            ))
    validator = HedNWBValidator(nwbfile.lab_meta_data["hed_schema"])
    # assemble=False: ndx-hed 0.3.0 cannot assemble the rows of a table with a DynamicTableRegion column
    # (get_bids_dataframe compares array cells with ""), and optogenetic_epochs has one (optogenetic_sites).
    # Each HED string and each column is still validated.
    issues = validator.validate_file(nwbfile, ErrorHandler(check_for_warnings=True), assemble=False)
    result["hed_issues"] = get_printable_issue_string(issues) if issues else ""
print(json.dumps(result))
"""


def _check_meanings_and_hed(nwbfile_path: Path, annotations: dict) -> dict:
    """Every value in an annotated column has exactly one row in its MeaningsTable, and the HED validates.

    Returns the values in the file of each annotated column.
    """
    completed = subprocess.run(
        [sys.executable, "-c", READ_MEANINGS_SCRIPT, str(nwbfile_path)], capture_output=True, text=True, check=True
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["hed_issues"] == ""

    found = {}
    for table in result["tables"]:
        label = (table["table"], table["column"])
        described = table["values"]
        assert len(described) == len(set(described)), label
        assert set(table["in_file"]) <= set(described), (label, set(table["in_file"]) - set(described))
        expected = annotations["tables"][label[0]][label[1]]
        assert set(described) == set(expected)
        for value, meaning, hed in zip(described, table["meanings"], table["hed"]):
            assert meaning == expected[value]["meaning"]
            assert hed == expected[value].get("hed", "")
        found[label] = set(table["in_file"])
    return found


@pytest.mark.parametrize("hed_string_owner", SUB_CONVERSIONS_WITH_MEANINGS)
def test_every_hed_string_validates(hed_string_owner):
    from hed import HedString, load_schema_version
    from hed.validator import HedValidator

    annotations = _load_annotations(hed_string_owner)
    schema = load_schema_version(annotations["hed_schema_version"])
    validator = HedValidator(schema)
    for table_name, columns in annotations["tables"].items():
        for column_name, entries in columns.items():
            for entry in entries.values():
                # The interface writes the meanings of the reaching event types itself
                if (table_name, column_name) != ("reaching_events", "label"):
                    assert entry["meaning"]
                if entry.get("hed"):
                    issues = validator.validate(
                        HedString(entry["hed"], schema),
                        allow_placeholders=False,
                        error_handler=ErrorHandler(check_for_warnings=True),
                    )
                    assert not issues, get_printable_issue_string(issues)


def test_reaching_meanings_match_the_event_descriptions():
    """The two reaching sub-conversions share the interface, so their annotations are the same."""
    assert _load_annotations("reaching_test") == _load_annotations("water_consumption")
    labels = set(_load_annotations("reaching_test")["tables"]["reaching_events"]["label"])
    assert labels == set(behaviorinterface.DEFAULT_EVENT_TYPE_DESCRIPTIONS)
    paws = set(_load_annotations("reaching_test")["tables"]["reaching_events"]["paw"])
    assert paws == set(behaviorinterface.PAW_NORMALIZATION.values()) | {"unknown"}


# A made-up annotation CSV with every event type and body-part code of the raw files, in the rich format
# (pixel columns written with dots, as in some raw files) and with one row that has nothing annotated.
REACHING_CSV = (
    "frame,paw,event.type,target.x,target.y,paw.x,paw.y,reference.px.,distance.px.,distance.cm.\n"
    "60,L,semi-drop,101,201,111,211,50,12.5,0.25\n"
    "10,L,C,102,202,112,212,50,10.0,0.2\n"
    "20,R,M,103,203,,,50,,\n"
    "30,L,missed,104,204,114,214,50,14.0,0.28\n"
    "40,mouth,E,105,205,115,215,50,15.0,0.3\n"
    "50,R,drop,106,206,116,216,50,16.0,0.32\n"
    "70,,,,,,,,,\n"
)
# What each row must become: (frame, label, paw, target_x, paw_x, distance_cm), in time order
REACHING_ROWS = [
    (10, "correct", "left", 102.0, 112.0, 0.2),
    (20, "miss", "right", 103.0, np.nan, np.nan),
    (30, "miss", "left", 104.0, 114.0, 0.28),
    (40, "empty", "mouth", 105.0, 115.0, 0.3),
    (50, "drop", "right", 106.0, 116.0, 0.32),
    (60, "semidrop", "left", 101.0, 111.0, 0.25),
    (70, "unknown", "unknown", np.nan, np.nan, np.nan),
]


@pytest.mark.parametrize("sub_conversion_name", ["reaching_test", "water_consumption"])
def test_reaching_events_annotations(sub_conversion_name, tmp_path, monkeypatch):
    annotation_file_path = tmp_path / "session_behavior.csv"
    annotation_file_path.write_text(REACHING_CSV)
    frame_rate = 60.0
    monkeypatch.setattr(behaviorinterface, "get_video_timestamps", lambda file_path: np.arange(1000) / frame_rate)
    behavior_metadata_path = PACKAGE_PATH / sub_conversion_name / "behavior_metadata.yaml"
    interface = ReachingBehaviorInterface(
        file_path=annotation_file_path,
        video_file_path=tmp_path / "session.avi",
        metadata_yaml_path=behavior_metadata_path,
    )
    nwbfile = _make_nwbfile(sub_conversion_name, genotype="DAT-Cre")
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    annotations = _load_annotations(sub_conversion_name)
    add_value_meanings(nwbfile=nwbfile, annotations=annotations)
    add_external_resources(nwbfile=nwbfile, terms=_load_terms(sub_conversion_name))
    nwbfile_path = tmp_path / "session.nwb"
    # Written the way NeuroConv's run_conversion writes it (with its default HDF5 backend configuration)
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    # Read back in this process, with every package of the conversion imported
    event_descriptions = load_dict_from_file(behavior_metadata_path)["Behavior"]["ReachingEvents"]["EventTypes"]
    expected_meanings = {
        "label": {label: entry["description"].strip() for label, entry in event_descriptions.items()},
        "paw": {value: entry["meaning"] for value, entry in annotations["tables"]["reaching_events"]["paw"].items()},
    }
    with NWBHDF5IO(nwbfile_path, "r") as io:
        read_nwbfile = io.read()
        reach_events = read_nwbfile.processing["behavior"]["reaching_events"]
        assert isinstance(reach_events, EventsTable)
        assert reach_events["timestamp"].resolution == 1.0 / frame_rate

        # Every annotated event is a row, in time order, with all of its values
        table = reach_events.to_dataframe()
        assert len(table) == len(REACHING_ROWS)
        for (_, row), (frame, label, paw, target_x, paw_x, distance_cm) in zip(table.iterrows(), REACHING_ROWS):
            assert row["timestamp"] == frame / frame_rate
            assert (row["frame"], row["label"], row["paw"]) == (frame, label, paw)
            np.testing.assert_equal([row["target_x"], row["paw_x"], row["distance_cm"]], [target_x, paw_x, distance_cm])
        assert table.loc[
            table["frame"] == 10, ["target_y", "paw_y", "reference_px", "distance_px"]
        ].values.tolist() == [[202.0, 212.0, 50.0, 10.0]]

        # The MeaningsTables survive the round trip and describe every value of their column
        assert set(reach_events.meanings_tables) == {"label_meanings", "paw_meanings"}
        for column_name in ["label", "paw"]:
            meanings_table = reach_events.get_meanings_for_column(column_name)
            values = meanings_table["value"].data[:].tolist()
            assert len(values) == len(set(values))
            assert set(table[column_name]) <= set(values)
            assert dict(zip(values, meanings_table["meaning"].data[:])) == expected_meanings[column_name]
            expected_hed = {
                value: entry.get("hed", "")
                for value, entry in annotations["tables"]["reaching_events"][column_name].items()
            }
            assert dict(zip(values, meanings_table["HED"].data[:])) == expected_hed

        # HED validates, with the HED of each row assembled from its label and its paw
        validator = HedNWBValidator(read_nwbfile.lab_meta_data["hed_schema"])
        issues = validator.validate_file(read_nwbfile, ErrorHandler(check_for_warnings=True), assemble=True)
        assert not issues, get_printable_issue_string(issues)


def test_opto_dlight_session_on_made_up_data(tmp_path):
    """Run the opto+dLight conversion on made-up TTL and signal files and check the annotations it writes."""
    from meletis_lab_to_nwb.opto_dlight.convert_session import session_to_nwb

    frame_rate = 30.0
    n_frames = 900
    ttl = np.zeros(n_frames, dtype=bool)
    ttl[100:280] = True  # the sync pulse at the start (6 s), not a stimulation
    ttl[400:430] = True  # two 1 s stimulation bursts
    ttl[600:630] = True
    ttl_file_path = tmp_path / "opto_2024-03-01T10_16_32.csv"
    start = datetime.datetime(2024, 3, 1, 10, 16, 32)
    ttl_file_path.write_text(
        "".join(
            f"{(start + datetime.timedelta(seconds=frame / frame_rate)).isoformat()},{frame},{value}\n"
            for frame, value in enumerate(ttl)
        )
    )
    signal_file_path = tmp_path / "opto_2024-03-01T10_16_32_signal_df.csv"
    times = np.arange(600) / 20.0
    signal_file_path.write_text("Time(s),sig\n" + "".join(f"{time:.2f},{np.sin(time):.4f}\n" for time in times))
    details_row = {
        "mouse.ID": "700_001",
        "DoB": "01-Jan-24",
        "sex": "m",
        "group": "dStr",
        "line": "anxa1-flp",
        "intenisty": "1",  # codespell:ignore intenisty (the column name in details.csv)
        "frequency": "40",
        "start.fp": "100",
    }
    session_to_nwb(
        ttl_file_path=ttl_file_path,
        signal_file_path=signal_file_path,
        output_dir_path=tmp_path / "output",
        details_row=details_row,
        verbose=False,
    )
    nwbfile_path = tmp_path / "output" / "sub-700-001" / "sub-700-001_ses-opto-2024-03-01T10-16-32.nwb"

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert nwbfile.subject.genotype == "Anxa1-Flp"
        assert nwbfile.subject.strain == "C57BL/6N"
        names = {}
        for neurodata_object in nwbfile.all_children():
            parent = neurodata_object.parent
            names[neurodata_object.object_id] = (
                neurodata_object.name if parent is None else f"{parent.name}/{neurodata_object.name}"
            )
        references = nwbfile.external_resources.to_dataframe()
        references["object"] = references["object_id"].map(names)
        references = _reference_set(references)

    assert ("fiber_photometry_table/location", "", "Dorsal caudoputamen", "MBA:672") in references
    for hemisphere in ["left", "right"]:
        injection = (f"optogenetic_virus_injections/snc_injection_{hemisphere}", "location")
        assert (*injection, "Substantia nigra, compact part", "MBA:374") in references
    assert ("root/subject", "species", "Mus musculus", "NCBITaxon:10090") in references
    assert not any(reference[1] == "strain" for reference in references)

    found = _check_meanings_and_hed(nwbfile_path, _load_annotations("opto_dlight"))
    assert found == {("optogenetic_epochs", "stimulation_on"): {True}}
