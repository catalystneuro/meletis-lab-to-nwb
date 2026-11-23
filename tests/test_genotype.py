"""Tests for the genotype handling shared by all sub-conversions. They use small made-up tables."""

from pathlib import Path

import pytest

from meletis_lab_to_nwb.genotype import (
    check_genotype_consistency,
    find_genotype_conflicts,
    normalize_genotype,
    read_genotype_per_subject,
)

SUB_CONVERSION_NAMES = [
    "arrow_maze_choice_task",
    "open_field_test",
    "opto_dlight",
    "reaching_test",
    "water_consumption",
]
PACKAGE_PATH = Path(__file__).parent.parent / "src" / "meletis_lab_to_nwb"


def _write_details_file(folder_path: Path, rows: list[tuple[str, str]]) -> Path:
    folder_path.mkdir(parents=True, exist_ok=True)
    details_file_path = folder_path / "details.csv"
    lines = ["video,mouse.ID,group,line"]
    lines += [f"video_{index},{mouse_id},group,{line}" for index, (mouse_id, line) in enumerate(rows)]
    details_file_path.write_text("\n".join(lines) + "\n")
    return details_file_path


@pytest.mark.parametrize(
    "line, expected",
    [
        # The spellings found in the published files of DANDI:001828.
        ("anxa1-flp", "Anxa1-Flp"),
        ("Anxa1-flp", "Anxa1-Flp"),
        ("dat-cre", "DAT-Cre"),
        ("dat_cre", "DAT-Cre"),
        ("Dat_cre", "DAT-Cre"),
        ("WT", "WT"),
        ("Wt", "WT"),
        ("Anxa1-flp/DAT-cre", "Anxa1-Flp/DAT-Cre"),
        ("DAT-cre/Tfam", "DAT-Cre/Tfam"),
        # Spaces around the value or around a part.
        ("  anxa1-flp ", "Anxa1-Flp"),
        ("Anxa1-flp / DAT-cre", "Anxa1-Flp/DAT-Cre"),
        # A line that is not in the table is kept as written.
        ("Vglut2-cre", "Vglut2-cre"),
        # Empty and missing values.
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_normalize_genotype(line, expected):
    assert normalize_genotype(line) == expected


def test_normalize_genotype_is_stable():
    for line in ["anxa1-flp", "Dat_cre", "Wt", "DAT-cre/Tfam", "Vglut2-cre"]:
        genotype = normalize_genotype(line)
        assert normalize_genotype(genotype) == genotype


@pytest.mark.parametrize("sub_conversion_name", SUB_CONVERSION_NAMES)
def test_every_sub_conversion_uses_the_shared_functions(sub_conversion_name):
    convert_session_text = (PACKAGE_PATH / sub_conversion_name / "convert_session.py").read_text()
    assert "normalize_genotype(details_row" in convert_session_text

    convert_all_sessions_text = (PACKAGE_PATH / sub_conversion_name / "convert_all_sessions.py").read_text()
    assert "check_genotype_consistency(data_dir_path=data_dir_path)" in convert_all_sessions_text


def test_read_genotype_per_subject(tmp_path):
    details_file_path = _write_details_file(
        tmp_path / "oft",
        [("661_506", "anxa1-flp"), ("661_506", "Anxa1-flp"), ("700001", "WT"), ("700002", ""), ("", "WT")],
    )

    assert read_genotype_per_subject(details_file_path) == {"661-506": {"Anxa1-Flp"}, "700001": {"WT"}}


def test_read_genotype_per_subject_without_line_column(tmp_path):
    folder_path = tmp_path / "other"
    folder_path.mkdir()
    (folder_path / "details.csv").write_text("name,value\na,1\n")

    assert read_genotype_per_subject(folder_path / "details.csv") == {}


def test_spelling_differences_are_not_conflicts(tmp_path):
    details_file_paths = [
        _write_details_file(tmp_path / "oft", [("700001", "anxa1-flp"), ("700002", "dat-cre"), ("700003", "WT")]),
        _write_details_file(tmp_path / "water_consumption", [("700001", "Anxa1-flp"), ("700002", "dat_cre")]),
        _write_details_file(tmp_path / "reaching_test", [("700001", " ANXA1-FLP"), ("700003", "wt")]),
    ]

    assert find_genotype_conflicts(details_file_paths) == {}
    for folder_name in ["oft", "water_consumption", "reaching_test"]:
        check_genotype_consistency(data_dir_path=tmp_path / folder_name)


def test_different_lines_for_one_subject_are_found(tmp_path):
    details_file_paths = [
        _write_details_file(tmp_path / "oft", [("700001", "anxa1-flp"), ("700002", "WT"), ("700003", "WT")]),
        _write_details_file(tmp_path / "water_consumption", [("700001", "dat_cre"), ("700002", "anxa1-flp")]),
        _write_details_file(tmp_path / "opto+dLight", [("700002", "anxa1-flp")]),
        _write_details_file(tmp_path / "tmaze", [("700003", "WT"), ("700004", "anxa1-flp")]),
    ]

    assert find_genotype_conflicts(details_file_paths) == {
        "700001": {"Anxa1-Flp": ["oft"], "DAT-Cre": ["water_consumption"]},
        "700002": {"Anxa1-Flp": ["opto+dLight", "water_consumption"], "WT": ["oft"]},
    }


def test_check_fails_for_a_subject_with_two_lines(tmp_path):
    _write_details_file(tmp_path / "oft", [("700001", "anxa1-flp"), ("700002", "WT"), ("700003", "WT")])
    _write_details_file(tmp_path / "water_consumption", [("700001", "dat_cre"), ("700002", "anxa1-flp")])
    _write_details_file(tmp_path / "tmaze", [("700003", "WT"), ("700004", "anxa1-flp")])

    with pytest.raises(ValueError) as error_info:
        check_genotype_consistency(data_dir_path=tmp_path / "oft")
    message = str(error_info.value)
    assert "2 subject(s) of 'oft'" in message
    assert "700001: 'Anxa1-Flp' in oft; 'DAT-Cre' in water_consumption" in message
    assert "700002: 'Anxa1-Flp' in water_consumption; 'WT' in oft" in message
    assert "700003" not in message

    with pytest.raises(ValueError, match="2 subject"):
        check_genotype_consistency(data_dir_path=tmp_path / "water_consumption")


def test_check_only_covers_the_subjects_of_the_sub_experiment(tmp_path):
    _write_details_file(tmp_path / "oft", [("700001", "anxa1-flp")])
    _write_details_file(tmp_path / "water_consumption", [("700001", "dat_cre")])
    _write_details_file(tmp_path / "tmaze", [("700003", "WT"), ("700004", "anxa1-flp")])

    # No subject of the arrow maze folder is affected by the conflict between the other two folders.
    check_genotype_consistency(data_dir_path=tmp_path / "tmaze")


def test_check_fails_for_two_lines_within_one_file(tmp_path):
    _write_details_file(tmp_path / "oft", [("700001", "anxa1-flp"), ("700001", "WT")])

    with pytest.raises(ValueError, match="700001: 'Anxa1-Flp' in oft; 'WT' in oft"):
        check_genotype_consistency(data_dir_path=tmp_path / "oft")
