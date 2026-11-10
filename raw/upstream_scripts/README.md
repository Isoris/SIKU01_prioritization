# upstream_scripts

Written for: readers who want to know how the upstream tools were called.

Retrieval of the genomes that Panaroo was run on.

These scripts are the v30 pipeline's calls to the external tools (stage scripts of the general pipeline `PANGENOME_VACCINE_PIPELINE_v30`). They are kept here because they are the only executable form of those calls in this deposit: the capsule's own scripts parse and tabulate the tools' output, and the tools ran outside the capsule (see `analysis.yaml`, `OPEN.md`). They are provenance: they were **not executed** for this deposit, their settings are not shown to be identical to the runs behind the reported tables, and the pipeline folder that held them no longer runs these stages. Copied unchanged (sha256 in `SHA256.txt`).

| file | what it does |
|---|---|
| `01_fetch_genomes_NCBI.py` | retrieval of genome assemblies and annotations from NCBI (datasets CLI) |
