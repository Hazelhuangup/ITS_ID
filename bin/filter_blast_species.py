#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NO_HIT_RESULTS = {"No_alignment", "Not_extracted"}


@dataclass(frozen=True)
class MetadataName:
    current_name: str
    comparison_name: str | None


def sample_name(path: Path) -> str:
    name = path.name
    if ".m6" in name:
        return name.split(".m6", 1)[0]
    return path.stem


def species_text(subject_id: str) -> str | None:
    try:
        after_species = subject_id.split("s__", 1)[1]
        return after_species.split("|SH", 1)[0]
    except IndexError:
        return None


def normalise_original_name(name: object) -> str | None:
    if pd.isna(name):
        return None

    text = re.sub(r"\s+", " ", str(name).replace("\xa0", " ")).strip()
    words = text.split()
    if len(words) < 2:
        return None
    return f"{words[0]}_{words[1]}"


def genus_from_species_name(name: str | None) -> str | None:
    if not name:
        return None
    return name.split("_", 1)[0]


def clean_current_name(name: object) -> str:
    if pd.isna(name):
        return "NA"
    text = re.sub(r"\s+", " ", str(name).replace("\xa0", " ")).strip()
    return text.replace(" ", "_") if text else "NA"


def load_metadata(path: Path) -> dict[str, MetadataName]:
    metadata = pd.read_excel(path, dtype={"EG_ID": str})
    required_columns = {"EG_ID", "Current name.x"}
    missing = required_columns.difference(metadata.columns)
    if missing:
        raise ValueError(f"Missing required metadata columns: {', '.join(sorted(missing))}")

    names: dict[str, MetadataName] = {}
    for _, row in metadata.iterrows():
        eg_id = str(row["EG_ID"]).strip()
        current_name = clean_current_name(row["Current name.x"])
        comparison_name = normalise_original_name(row["Current name.x"])
        if eg_id:
            names[eg_id] = MetadataName(current_name, comparison_name)
    return names


def load_unite_names(path: Path) -> tuple[set[str], set[str]]:
    species_names: set[str] = set()
    genus_names: set[str] = set()

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            name = line.strip()
            if not name:
                continue
            species_names.add(name)
            genus = genus_from_species_name(name)
            if genus:
                genus_names.add(genus)

    return species_names, genus_names


def load_itsx_failures(path: Path) -> set[str]:
    if not path.exists():
        return set()

    failures: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            sample = line.strip().split("\t", 1)[0]
            if sample:
                failures.add(sample)
    return failures


def species_call(path: Path) -> tuple[str, set[str], set[str]]:
    species_names: set[str] = set()
    genus_names: set[str] = set()

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue

            fields = line.split("\t")
            if len(fields) < 3:
                continue

            try:
                identity = float(fields[2])
            except ValueError:
                continue

            if identity <= 97:
                continue

            subject_id = fields[1]
            name = species_text(subject_id)
            genus = genus_from_species_name(name)
            if genus:
                genus_names.add(genus)

            if "_sp|SH" in subject_id:
                continue

            if name:
                species_names.add(name)

    if not species_names:
        return "No_alignment", species_names, genus_names
    if len(species_names) == 1:
        return next(iter(species_names)), species_names, genus_names
    return "Multiple", species_names, genus_names


def compare_call(blast_result: str, species_names: set[str], original_name: str | None) -> str:
    if blast_result in NO_HIT_RESULTS:
        return "NA"
    if not original_name:
        return "NA"
    if blast_result == "Multiple":
        return "Include" if original_name in species_names else "Mismatch"
    return "Match" if blast_result == original_name else "Mismatch"


def compare_genus(
    blast_result: str, genus_names: set[str], original_name: str | None
) -> str:
    if blast_result in NO_HIT_RESULTS:
        return "NA"
    original_genus = genus_from_species_name(original_name)
    if original_genus and original_genus in genus_names:
        return "Match"
    return "Mismatch"


def database_status(value: str | None, database_values: set[str], should_check: bool) -> str:
    if not should_check:
        return "NA"
    if not value:
        return "No"
    return "Yes" if value in database_values else "No"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise BLAST m6.tsv files by high-identity species calls."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=PROJECT_ROOT / "01_data" / "06_EG_002",
        type=Path,
        help="Directory containing *.m6.tsv files. Default: 01_data/06_EG_002",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        default=PROJECT_ROOT / "01_data" / "Metadata_for_samples.xlsx",
        type=Path,
        help="Metadata Excel file. Default: 01_data/Metadata_for_samples.xlsx",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=PROJECT_ROOT / "03_output" / "06_EG_002_ITS_match_to_UNITE.tsv",
        type=Path,
        help="Output TSV file. Default: 03_output/06_EG_002_ITS_match_to_UNITE.tsv",
    )
    parser.add_argument(
        "-u",
        "--unite-names",
        default=PROJECT_ROOT / "01_data" / "UNITE_public_19.02.2025.id.txt",
        type=Path,
        help="UNITE species name list. Default: 01_data/UNITE_public_19.02.2025.id.txt",
    )
    parser.add_argument(
        "-f",
        "--itsx-fail",
        default=PROJECT_ROOT / "01_data" / "ITSx_fail.tsv",
        type=Path,
        help="Sample IDs where ITS extraction failed. Default: 01_data/ITSx_fail.tsv",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    files = sorted(input_dir.glob("*.m6.tsv"), key=lambda p: p.name)
    metadata_names = load_metadata(args.metadata)
    unite_species_names, unite_genus_names = load_unite_names(args.unite_names)
    itsx_failures = load_itsx_failures(args.itsx_fail)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        out.write(
            "Sample\tBLAST_species\tCurrent_name\tSpecies_match\tGenus_match\t"
            "Species_in_UNITE\tGenus_in_UNITE\n"
        )
        for path in files:
            sample = sample_name(path)
            if sample in itsx_failures:
                blast_result = "Not_extracted"
                species_names: set[str] = set()
                genus_names: set[str] = set()
            else:
                blast_result, species_names, genus_names = species_call(path)
            metadata_name = metadata_names.get(sample)
            current_name = metadata_name.current_name if metadata_name else "NA"
            comparison_name = metadata_name.comparison_name if metadata_name else None
            comparison = compare_call(blast_result, species_names, comparison_name)
            if comparison == "NA":
                genus_comparison = "NA"
            else:
                genus_comparison = compare_genus(
                    blast_result, genus_names, comparison_name
                )
            original_genus = genus_from_species_name(comparison_name)
            species_in_database = database_status(
                comparison_name, unite_species_names, comparison == "Mismatch"
            )
            genus_in_database = database_status(
                original_genus, unite_genus_names, genus_comparison == "Mismatch"
            )
            out.write(
                f"{sample}\t{blast_result}\t{current_name}\t{comparison}\t"
                f"{genus_comparison}\t{species_in_database}\t{genus_in_database}\n"
            )


if __name__ == "__main__":
    main()
