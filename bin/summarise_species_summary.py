#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "Sample",
    "BLAST_species",
    "Current_name",
    "Species_match",
    "Genus_match",
    "Species_in_UNITE",
    "Genus_in_UNITE",
]
SUMMARY_COLUMNS = COLUMNS[3:7]
CATEGORY_ORDERS = {
    "Species_match": ["Match", "Include", "Mismatch", "NA"],
    "Genus_match": ["Match", "Include", "Mismatch", "NA"],
    "Species_in_UNITE": ["Yes", "No", "NA"],
    "Genus_in_UNITE": ["Yes", "No", "NA"],
}


def count_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    count_map = df[column].value_counts(dropna=False).to_dict()
    ordered_categories = CATEGORY_ORDERS[column]
    counts = pd.DataFrame(
        {
            column: ordered_categories,
            "Count": [count_map.get(category, 0) for category in ordered_categories],
        }
    )
    counts["Percent"] = counts["Count"] / len(df) * 100
    return counts


def write_excel(summaries: dict[str, pd.DataFrame], output_path: Path) -> None:
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        combined = pd.concat(
            [
                summary.assign(Column=column).rename(columns={column: "Category"})[
                    ["Column", "Category", "Count", "Percent"]
                ]
                for column, summary in summaries.items()
            ],
            ignore_index=True,
        )
        combined.to_excel(writer, sheet_name="All_summary", index=False)

        for column, summary in summaries.items():
            summary.to_excel(writer, sheet_name=column, index=False)


def write_pdf(summaries: dict[str, pd.DataFrame], output_path: Path) -> None:
    width, height = 792, 612
    panel_positions = [
        (65, 335),
        (435, 335),
        (65, 70),
        (435, 70),
    ]
    chart_width, chart_height = 265, 170
    commands = []

    for (column, summary), (left, bottom) in zip(summaries.items(), panel_positions):
        plot_summary = summary[summary["Count"] > 0]
        categories = plot_summary[column].astype(str).tolist()
        counts = plot_summary["Count"].astype(int).tolist()
        max_count = max(counts)
        gap = 30
        full_bar_width = (chart_width - gap * (len(counts) - 1)) / len(counts)
        bar_width = full_bar_width * 0.55

        commands.extend(
            [
                f"BT /F1 16 Tf {left:.2f} {bottom + chart_height + 42:.2f} Td "
                + pdf_text(column)
                + " Tj ET",
                "1 w 0 0 0 RG",
                f"{left} {bottom} m {left + chart_width} {bottom} l S",
                f"{left} {bottom} m {left} {bottom + chart_height} l S",
            ]
        )

        for idx, (category, count) in enumerate(zip(categories, counts)):
            slot_x = left + idx * (full_bar_width + gap)
            x = slot_x + (full_bar_width - bar_width) / 2
            label_x = slot_x + full_bar_width / 2 - estimated_text_width(category, 11) / 2
            count_x = x + bar_width / 2 - estimated_text_width(str(count), 12) / 2
            bar_height = chart_height * count / max_count
            commands.extend(
                [
                    "0.298 0.471 0.659 rg",
                    f"{x:.2f} {bottom:.2f} {bar_width:.2f} {bar_height:.2f} re f",
                    "0 0 0 rg",
                    f"BT /F1 12 Tf {count_x:.2f} "
                    f"{bottom + bar_height + 7:.2f} Td "
                    + pdf_text(str(count))
                    + " Tj ET",
                    f"BT /F1 11 Tf {label_x:.2f} {bottom - 22:.2f} Td "
                    + pdf_text(category)
                    + " Tj ET",
                ]
            )

        commands.extend(
            [
                f"BT /F1 12 Tf {left - 44:.2f} {bottom + chart_height / 2:.2f} Td "
                + pdf_text("Count")
                + " Tj ET",
            ]
        )

    write_simple_pdf(output_path, ["\n".join(commands)], width, height)


def pdf_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})"


def estimated_text_width(text: str, font_size: int) -> float:
    return len(text) * font_size * 0.52


def write_simple_pdf(output_path: Path, pages: list[str], width: int, height: int) -> None:
    objects: list[bytes] = []
    page_object_ids: list[int] = []
    content_object_ids: list[int] = []

    font_id = 3
    next_id = 4
    for _ in pages:
        page_object_ids.append(next_id)
        content_object_ids.append(next_id + 1)
        next_id += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_id, content_id, content in zip(page_object_ids, content_object_ids, pages):
        stream = content.encode("latin-1", errors="replace")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode()
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    output_path.write_bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Excel and PDF summaries for species summary columns 4-7."
    )
    parser.add_argument(
        "summary_tsv",
        nargs="?",
        default=PROJECT_ROOT / "03_output" / "06_EG_002_ITS_match_to_UNITE.tsv",
        type=Path,
        help="Input summary TSV. Default: 03_output/06_EG_002_ITS_match_to_UNITE.tsv",
    )
    parser.add_argument(
        "-x",
        "--excel",
        default=PROJECT_ROOT / "03_output" / "06_EG_002_ITS_match_to_UNITE_summary.xlsx",
        type=Path,
        help="Output Excel file. Default: 03_output/06_EG_002_ITS_match_to_UNITE_summary.xlsx",
    )
    parser.add_argument(
        "-p",
        "--pdf",
        default=PROJECT_ROOT / "03_output" / "06_EG_002_ITS_match_to_UNITE_summary.pdf",
        type=Path,
        help="Output PDF file. Default: 03_output/06_EG_002_ITS_match_to_UNITE_summary.pdf",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.summary_tsv, sep="\t", keep_default_na=False)
    if list(df.columns) != COLUMNS:
        df = pd.read_csv(
            args.summary_tsv,
            sep="\t",
            header=None,
            names=COLUMNS,
            keep_default_na=False,
        )
    summaries = {column: count_column(df, column) for column in SUMMARY_COLUMNS}

    args.excel.parent.mkdir(parents=True, exist_ok=True)
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    write_excel(summaries, args.excel)
    write_pdf(summaries, args.pdf)


if __name__ == "__main__":
    main()
