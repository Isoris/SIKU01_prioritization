"""The test specification in specification/ agrees with the rules and with the files of this repository."""
import csv
import hashlib
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "specification")
TAB = chr(9)


def table(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=TAB))


class Specification(unittest.TestCase):
    def setUp(self):
        self.rules = table(os.path.join(ROOT, "rules", "ranking_rules_v27.tsv"))
        self.binding = table(os.path.join(SPEC, "test_implementation_binding_v03.tsv"))
        self.here = table(os.path.join(SPEC, "test_binding_in_this_repository.tsv"))

    def test_tables_are_the_deposited_ones(self):
        rows = table(os.path.join(SPEC, "CHECKSUMS.tsv"))
        self.assertEqual(len(rows), 5)
        for row in rows:
            with open(os.path.join(SPEC, row["file"]), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), row["sha256"], row["file"])

    def test_every_bound_rule_is_a_rule(self):
        ids = {r["rule_id"] for r in self.rules}
        self.assertEqual(len(self.binding), 32)
        for b in self.binding:
            self.assertIn(b["rule_id"], ids, b["test_id"])

    def test_every_gate_and_component_has_a_bound_test(self):
        bound = {b["rule_id"] for b in self.binding if b["resolved_test_file"]}
        for r in self.rules:
            if r["role"] in ("hard", "additive"):
                self.assertIn(r["rule_id"], bound, r["rule_id"])

    def test_the_repository_table_matches_the_binding_and_the_files(self):
        self.assertEqual([(b["test_id"], b["rule_id"], b["resolved_test_file"]) for b in self.binding],
                         [(h["test_id"], h["rule_id"], h["original_test_file"]) for h in self.here])
        for h in self.here:
            f = h["file_in_this_repository"]
            if f.startswith("tests/"):
                self.assertTrue(os.path.exists(os.path.join(ROOT, *f.split("/"))), f)
            for part in h["related_test_in_this_repository"].split(";"):
                name = part.strip().split(" ")[0]
                if name:
                    self.assertTrue(os.path.exists(os.path.join(ROOT, *name.split("/"))), name)


if __name__ == "__main__":
    unittest.main()
