#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -B 02_scr/filter_blast_species.py
python3 -B 02_scr/summarise_species_summary.py
