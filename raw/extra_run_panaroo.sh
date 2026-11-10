panaroo -i dataset_gff3/*.gff \
  -o results_panaroo_95core_85fam \
  --clean-mode strict \
  --remove-invalid-genes \
  -a core \
  --aligner mafft \
  --core_threshold 0.95 \
  --family_threshold 0.85 \
  -t 20

python concatenate_core_genome.py \
  -o results_panaroo_95core_85fam \
  --core_threshold 0.95 \
  --prefix panaroo_core
