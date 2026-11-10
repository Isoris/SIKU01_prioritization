#!/usr/bin/env python3
"""run_A6434_canonical_v01.py - the capsule's declared entry point.

Runs analysis.yaml canonical_run.scripts in the declared order, from the capsule root. It exists
because the capsule declares its order under canonical_run and the bundle runner reads
execution.entrypoint; without an entry point the generated run_all.sh stops before any stage.

A step whose declared upstream input is not in this deposit is reported SKIPPED_MISSING_UPSTREAM
and does not stop the run, because the upstream product it would rebuild is already deposited.
Every other failure stops the run and the exit code is non-zero. The skip is always printed and
always listed in the summary, so a partial deposit is visible rather than silent.

Usage:  python3 02_code/run_A6434_canonical_v01.py [capsule_root]
"""
from __future__ import annotations
import subprocess, sys, os
from pathlib import Path
import yaml

# A step that needs an upstream product this deposit may not carry, with the file it reads.
NEEDS_UPSTREAM = {
    '02_code/build_literature_by_pangenome_id_v01.py':
        '08_source_data/routed_input/ST_A6035_02_protein_literature_assignments_v01.tsv',
    '02_code/code_A6434_conform_heuristic_inputs_v01.py':
        '04_tables/candidate_data_v01.tsv',
}
# A step that takes the capsule root as its first argument.
TAKES_CAPSULE_ARG = {'02_code/code_A6434_freeze_sweeps_v02_v01.py'}


def main() -> int:
    cap = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    a = yaml.safe_load((cap / 'analysis.yaml').read_text(encoding='utf-8'))['analysis']
    scripts = (a.get('canonical_run') or {}).get('scripts') or []
    if not scripts:
        print('no canonical_run.scripts declared in analysis.yaml', file=sys.stderr)
        return 2
    results = []
    for i, rel in enumerate(scripts, 1):
        need = NEEDS_UPSTREAM.get(rel)
        if need and not (cap / need).is_file():
            print(f'[{i}/{len(scripts)}] SKIPPED_MISSING_UPSTREAM {rel}\n'
                  f'      needs {need}, which this deposit does not carry;\n'
                  f'      the product it rebuilds is deposited, so the run continues.')
            results.append((rel, 'SKIPPED_MISSING_UPSTREAM'))
            continue
        cmd = [sys.executable, str(cap / rel)] + ([str(cap)] if rel in TAKES_CAPSULE_ARG else [])
        print(f'[{i}/{len(scripts)}] {rel}')
        r = subprocess.run(cmd, cwd=str(cap))
        if r.returncode != 0:
            results.append((rel, f'FAILED rc={r.returncode}'))
            print(f'\ncanonical run stopped at {rel} (rc={r.returncode})', file=sys.stderr)
            _summary(results, len(scripts))
            return 1
        results.append((rel, 'OK'))
    _summary(results, len(scripts))
    return 0


def _summary(results, total):
    print('\n--- canonical run summary ---')
    for rel, st in results:
        print(f'  {st:26s} {rel}')
    ok = sum(1 for _, s in results if s == 'OK')
    sk = sum(1 for _, s in results if s.startswith('SKIPPED'))
    print(f'  {ok} ran, {sk} skipped for a missing upstream input, {total} declared')


if __name__ == '__main__':
    sys.exit(main())
