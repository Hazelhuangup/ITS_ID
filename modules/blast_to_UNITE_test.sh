#!/bin/bash

#SBATCH --job-name=blast_all
#SBATCH --output=blast_all.out
#SBATCH --error=blast_all.err
#SBATCH --mail-user=whuang@kew.org
#SBATCH --partition=medium
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G

echo "Starting job on \$HOSTNAME"

source /mnt/apps/users/whuang/conda/etc/profile.d/conda.sh
conda activate bioinfo
blastn -query /mnt/shared/projects/rbgk/projects/FSP/03_Output/05_Evolutionary_Analysis/01_ITS_extraction/06_EG_002/EGP017_25_043/EGP017_25_043.full.fasta -db /mnt/shared/projects/rbgk/projects/FSP/01_RefSeq/03_its/UNITE_public_19.02.2025.fasta -out EGP017_25_043.m6.tsv -outfmt 6 -evalue 1e-5 -perc_identity 90 -max_target_seqs 80 -num_threads 2

echo "Job finished"
