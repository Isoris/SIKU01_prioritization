"""Reading and writing tab-separated tables, and checksums. Every table is UTF-8 with LF line endings."""
import csv
import hashlib

csv.field_size_limit(2**31 - 1)   # some cells hold a whole protein sequence


def read_tsv(path):
    """A table as a list of dicts; every value is kept as the text in the file."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh, delimiter="\t")]


def write_tsv(path, rows, fields=None):
    """Write a list of dicts. Column order is that of the first row unless `fields` is given."""
    if not rows and fields is None:
        raise ValueError(f"nothing to write to {path}")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields or list(rows[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def sha256_file(path):
    """SHA-256 of the file's bytes as they are."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_lf(path):
    """SHA-256 after reading CRLF as LF, so a file written on Windows and one written on Linux compare equal."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def count_rows(path):
    """Number of data rows (lines after the header)."""
    with open(path, "rb") as fh:
        return max(fh.read().count(b"\n") - 1, 0)
