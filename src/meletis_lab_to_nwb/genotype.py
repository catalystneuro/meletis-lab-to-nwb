"""Subject genotype handling shared by all sub-conversions.

Every sub-experiment folder has its own ``details.csv`` with a ``line`` column, and the same
mouse can appear in more than one of them. The functions here give every sub-conversion the
same spelling for a mouse line and detect mice whose line differs between the files.
"""

import csv
from collections import defaultdict
from pathlib import Path

# One spelling per mouse line, keyed by the lower-case spelling with "_" replaced by "-".
# The details.csv files spell the same line in several ways (`anxa1-flp`, `Anxa1-flp`,
# `dat_cre`, `dat-cre`, `DAT-cre`, `WT`). The spellings used here are the ones in the
# metadata of this repository.
CANONICAL_LINE_NAMES = {
    "wt": "WT",
    "anxa1-flp": "Anxa1-Flp",
    "dat-cre": "DAT-Cre",
}


def normalize_genotype(line: str | None) -> str:
    """Return the genotype for a value of the ``line`` column of a ``details.csv`` file.

    Only the spelling is unified. The function does not decide which line a mouse belongs to.
    A crossed line written with "/" (for example ``Anxa1-flp/DAT-cre``) is handled part by part.
    A part that is not in ``CANONICAL_LINE_NAMES`` is kept as written (for example ``Tfam``).

    Parameters
    ----------
    line : str or None
        The value of the ``line`` column.

    Returns
    -------
    str
        The genotype, for example ``"Anxa1-Flp"``, ``"DAT-Cre"``, ``"WT"`` or ``"DAT-Cre/Tfam"``.
        An empty or missing value gives an empty string.
    """
    if line is None:
        return ""
    parts = [part.strip() for part in str(line).split("/")]
    return "/".join(CANONICAL_LINE_NAMES.get(part.lower().replace("_", "-"), part) for part in parts if part)


def read_genotype_per_subject(details_file_path: str | Path) -> dict[str, set[str]]:
    """Read the genotypes listed for every subject in one ``details.csv`` file.

    Parameters
    ----------
    details_file_path : str or Path
        Path to a ``details.csv`` file with the columns ``mouse.ID`` and ``line``.

    Returns
    -------
    dict[str, set[str]]
        The set of normalized genotypes for each subject ID. The subject ID is written as in
        the NWB files ("_" replaced by "-"). Rows with an empty ``mouse.ID`` or ``line`` are
        skipped. A file without the two columns gives an empty dictionary.
    """
    genotypes_per_subject = defaultdict(set)
    with open(details_file_path) as f:
        for row in csv.DictReader(f):
            subject_id = str(row.get("mouse.ID") or "").strip().replace("_", "-")
            genotype = normalize_genotype(row.get("line"))
            if subject_id and genotype:
                genotypes_per_subject[subject_id].add(genotype)
    return dict(genotypes_per_subject)


def find_genotype_conflicts(details_file_paths: list[str | Path]) -> dict[str, dict[str, list[str]]]:
    """Find the subjects that have more than one genotype across ``details.csv`` files.

    Parameters
    ----------
    details_file_paths : list of str or Path
        Paths to the ``details.csv`` files of the sub-experiments. Each file is named in the
        result by the name of its folder (for example ``oft`` or ``water_consumption``).

    Returns
    -------
    dict[str, dict[str, list[str]]]
        For each subject with more than one genotype, the folders that list each genotype,
        for example ``{"687662": {"Anxa1-Flp": ["oft"], "DAT-Cre": ["water_consumption"]}}``.
        The dictionary is empty when every subject has one genotype.
    """
    experiments_per_genotype_per_subject = defaultdict(lambda: defaultdict(list))
    for details_file_path in sorted(Path(file_path) for file_path in details_file_paths):
        experiment_name = details_file_path.parent.name
        for subject_id, genotypes in read_genotype_per_subject(details_file_path).items():
            for genotype in sorted(genotypes):
                experiments_per_genotype_per_subject[subject_id][genotype].append(experiment_name)

    return {
        subject_id: dict(sorted(experiments_per_genotype.items()))
        for subject_id, experiments_per_genotype in sorted(experiments_per_genotype_per_subject.items())
        if len(experiments_per_genotype) > 1
    }


def check_genotype_consistency(*, data_dir_path: str | Path) -> None:
    """Fail when a subject of this sub-experiment has more than one genotype.

    The ``details.csv`` of ``data_dir_path`` is compared with itself and with the ``details.csv``
    of every folder next to it (the other sub-experiments). Only subjects listed in
    ``data_dir_path / "details.csv"`` are checked. Which genotype is right for a mouse is for
    the lab to say, so nothing is chosen here.

    Parameters
    ----------
    data_dir_path : str or Path
        Path to the folder of one sub-experiment (for example ``.../Meletis/oft``).

    Raises
    ------
    ValueError
        If the ``line`` column gives more than one genotype for a subject of this sub-experiment.
    """
    data_dir_path = Path(data_dir_path)
    details_file_path = data_dir_path / "details.csv"
    details_file_paths = {details_file_path, *data_dir_path.parent.glob("*/details.csv")}

    subject_ids = set(read_genotype_per_subject(details_file_path))
    conflicts = {
        subject_id: experiments_per_genotype
        for subject_id, experiments_per_genotype in find_genotype_conflicts(list(details_file_paths)).items()
        if subject_id in subject_ids
    }
    if not conflicts:
        return

    lines = []
    for subject_id, experiments_per_genotype in conflicts.items():
        genotypes = "; ".join(
            f"'{genotype}' in {', '.join(experiment_names)}"
            for genotype, experiment_names in experiments_per_genotype.items()
        )
        lines.append(f"  {subject_id}: {genotypes}")
    raise ValueError(
        f"The 'line' column of the details.csv files gives more than one genotype for {len(conflicts)} "
        f"subject(s) of '{data_dir_path.name}':\n"
        + "\n".join(lines)
        + "\nAsk the lab which genotype is right and correct the details.csv files before converting."
    )


# The wild-type mice were C57BL/6N mice from Charles River (Methods of doi:10.1101/2024.12.22.629963),
# so their strain is written with the vendor's code. The transgenic lines keep the strain in metadata.yaml.
WILD_TYPE_STRAIN = "C57BL/6NCrl"


def get_strain(genotype: str, default_strain: str | None) -> str | None:
    """Return the strain to write for a subject with this genotype.

    Parameters
    ----------
    genotype : str
        The genotype from :func:`normalize_genotype`.
    default_strain : str or None
        The strain in the metadata of the sub-conversion (``C57BL/6N``).

    Returns
    -------
    str or None
        ``WILD_TYPE_STRAIN`` for a wild-type subject (genotype ``WT``), otherwise ``default_strain``.
    """
    return WILD_TYPE_STRAIN if genotype == "WT" else default_strain
