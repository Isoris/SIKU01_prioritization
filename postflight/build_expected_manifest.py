#!/usr/bin/env python3
"""build_expected_manifest.py - (re)write expected_outputs/MANIFEST.tsv and expected_outputs/COLLECTION.sha256 from the files present.

Run it only when the expected outputs are changed on purpose (a rule, a parameter or the frozen frame changed and the change was
reviewed). The files in expected_outputs/ranking/ are the reference; this script measures them, it does not decide anything.

The manifest keeps four things apart:
  identity      file name, and where it was copied from (copied_from, source_sha256)
  integrity     sha256_lf_normalised (CRLF read as LF, so Windows and Linux agree), sha256_as_deposited (raw bytes), bytes
  content       count_unit + count: the number of data rows (lines minus the header), COUNTED here, not declared
  verification  count_method = counted, counted_by = this script; postflight recounts and recompares on every run

The collection fingerprint (COLLECTION.sha256) identifies the whole set of expected outputs with one value. Definition:
  text   = for every member of expected_outputs/ranking/ sorted by the bytewise order of its UTF-8 file name,
           the line  <file name> TAB <sha256_lf_normalised> LF
  hash   = SHA-256 of that text encoded as UTF-8 (LF line endings, trailing LF, nothing else: no sizes, counts or dates)
"""
import csv, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXP = os.path.join(ROOT, "expected_outputs")
RK = EXP   # the 21 result files sit directly in expected_outputs/; MANIFEST.tsv and COLLECTION.sha256 are not members
# where each expected output was taken from in the capsule (used when an earlier manifest does not already say)
CAPSULE = "capsules/ANL_A6434_CANDIDATE_RANKING/"
FROM = {"ranking_inputs_by_pangenome_id_v01.tsv": "01_analysis_output/derived/", "tbl_A6434_01_input_audit_v01.tsv": "04_tables/",
        "tbl_A6434_02_spine_exclusions_v01.tsv": "04_tables/"}
COLUMNS = ["file", "sha256_lf_normalised", "sha256_as_deposited", "bytes", "count_unit", "count", "count_method", "counted_by", "copied_from", "source_sha256"]


def collection_fingerprint(members):
    """members: iterable of (file name, sha256_lf). Returns (canonical text, sha256 hex). The definition is in the module docstring."""
    text = "".join("%s\t%s\n" % (n, h) for n, h in sorted(members, key=lambda m: m[0].encode("utf-8")))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def measure(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    lf = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(lf).hexdigest(), hashlib.sha256(raw).hexdigest(), len(raw), max(lf.count(b"\n") - 1, 0)


def main():
    old = {}
    mp = os.path.join(EXP, "MANIFEST.tsv")
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8", newline="") as fh:
            old = {r["file"]: r for r in csv.DictReader(fh, delimiter="\t")}
    rows = []
    for f in sorted(os.listdir(RK)):
        p = os.path.join(RK, f)
        if not os.path.isfile(p) or f in ("MANIFEST.tsv", "COLLECTION.sha256"):
            continue
        h_lf, h_raw, n, cnt = measure(p)
        prev = old.get(f, {})
        rows.append([f, h_lf, h_raw, n, "data_rows", cnt, "counted", "postflight/build_expected_manifest.py",
                     prev.get("copied_from") or (CAPSULE + FROM[f] + f if f in FROM else ""), prev.get("source_sha256") or prev.get("sha256_as_deposited") or h_raw])
    with open(mp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(rows)
    text, digest = collection_fingerprint((r[0], r[1]) for r in rows)
    with open(os.path.join(EXP, "COLLECTION.sha256"), "w", encoding="utf-8", newline="") as fh:
        fh.write("%s  expected_outputs (%d members; definition in postflight/build_expected_manifest.py)\n" % (digest, len(rows)))
    print("MANIFEST.tsv: %d members; collection fingerprint %s" % (len(rows), digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
