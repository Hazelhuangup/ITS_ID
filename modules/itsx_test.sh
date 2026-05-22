#!/bin/bash

#SBATCH --job-name=itsx_all
#SBATCH --output=itsx_all.out
#SBATCH --error=itsx_all.err
#SBATCH --mail-user=whuang@kew.org
#SBATCH --partition=medium
#SBATCH --cpus-per-task=48
#SBATCH --mem=2G

echo "Starting job on \$HOSTNAME"

source /mnt/apps/users/whuang/conda/etc/profile.d/conda.sh
conda activate itsx
ITSx -i ../01_genome_assemblies/EGP017_25_182_best_assembly.fa -o /mnt/shared/projects/rbgk/projects/FSP/02_src/05_Evolutionary_Analysis/01_ITS_extraction/03_test_output/EGP017_25_182_test_all --cpu 48

echo "Job finished"
