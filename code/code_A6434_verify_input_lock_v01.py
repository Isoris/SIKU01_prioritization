#!/usr/bin/env python3
"""Verify the frozen routed inputs of ANL_A6434 against the lock in route_manifest.tsv.

Run before every canonical execution:  ANL_ROOT=. python3 02_code/code_A6434_verify_input_lock_v01.py

Reads 08_source_data/routed_input/route_manifest.tsv, takes every row whose consumer_role starts with
"frozen_input", and recomputes the SHA-256 of its materialized_path. Exits 0 only when every locked file
is present and byte-identical to the lock. A missing or changed file is a refusal, never a silent
re-join: the pinned bytes are the only accepted evidence until an explicit rebase.

Status LOCKED_PRODUCER_DIVERGED and LOCKED_NO_PRODUCER_COPY_FOUND do not fail this check: they say the
upstream producer has moved or its copy is unlocated, which is a rebase / export question, not a
corruption of the frozen input. They are printed so they stay visible.
"""
import csv
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ANL_ROOT", ".")).resolve()
MANIFEST = ROOT / "08_source_data" / "routed_input" / "route_manifest.tsv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if not MANIFEST.is_file():
        print(f"REFUSED: {MANIFEST} not found")
        return 2
    bad = 0
    n = 0
    with open(MANIFEST, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if not (row.get("consumer_role") or "").startswith("frozen_input"):
                continue
            n += 1
            path = ROOT / row["materialized_path"]
            want = row["checksum"]
            if not path.is_file():
                print(f"MISSING   {row['input_name']}  {row['materialized_path']}")
                bad += 1
            elif sha256(path) != want:
                print(f"CHANGED   {row['input_name']}  expected {want[:12]}  found {sha256(path)[:12]}")
                bad += 1
            else:
                print(f"OK        {row['input_name']}  {row['status']}")
    print(f"{n} frozen inputs, {bad} failed")
    return 1 if bad or n == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
