"""The rule table and the comparison function: known answers for every rule."""
import shutil
import tempfile
import unittest
from pathlib import Path

from siku01_prioritization import layout, rules
from siku01_prioritization.tables import read_tsv, write_tsv

HERE = Path(__file__).resolve().parent
RULES, SYMBOL = rules.load_rules()
BY_ID = {r["rule_id"]: r for r in RULES}

# Every state an equality rule's variable can take, with the expected answer.
EQUALITY_TRUTH_TABLES = {
    "M0_ORF": [(1, True), ("1", True), (0, False)],
    "M0_PROTEIN_FORM": [("single", True), ("multiple", False), ("none", False)],
    "M2_TYPEIIS": [(0, True), ("0", True), (1, False), (3, False)],
    "M1_EPITOPE": [("yes", True), ("no", False)],
}


class RuleTable(unittest.TestCase):
    def test_23_rules(self):
        roles = [r["role"] for r in RULES]
        self.assertEqual((len(RULES), roles.count("declaration"), roles.count("hard"), roles.count("additive")), (23, 1, 14, 8))
        self.assertEqual(len(rules.executable(RULES)), 22)

    def test_routes_and_counts(self):
        for r in rules.executable(RULES):
            routes = rules.routes_of(r, layout.ROUTES)
            self.assertTrue(set(routes) <= set(layout.ROUTES), r["rule_id"])
            self.assertEqual(len(routes), int(r["n_routes"]), r["rule_id"])

    def test_rules_per_route(self):
        # hard gates / additive components that apply on each route
        want = {"silica": (9, 5), "cellulose": (9, 5), "aex": (9, 5), "cex": (9, 5), "pdna_tilapia": (8, 4), "pdna_zebrafish": (8, 4)}
        for route, (n_hard, n_add) in want.items():
            mine = [r for r in rules.executable(RULES) if route in rules.routes_of(r, layout.ROUTES)]
            self.assertEqual((sum(r["role"] == "hard" for r in mine), sum(r["role"] == "additive" for r in mine)), (n_hard, n_add), route)

    def test_every_variable_is_a_column_of_the_inputs(self):
        with open(layout.EXPECTED_TABLES / layout.T_RANKING_INPUTS, encoding="utf-8") as fh:
            header = fh.readline().rstrip("\n").split("\t")
        for r in rules.executable(RULES):
            self.assertIn(r["variable"], header, r["rule_id"])

    def test_symbolic_thresholds_resolve(self):
        symbolic = [r for r in rules.executable(RULES) if r["threshold"] in SYMBOL]
        self.assertEqual(sorted(r["rule_id"] for r in symbolic), ["M2_CAI", "M2_CAI_DR", "M2_CAI_ON", "M2_CDS_LEN", "M2_GC3"])
        for r in symbolic:
            thr, sym = rules.threshold_of(r, SYMBOL)
            self.assertIsInstance(thr, float)
            self.assertEqual(sym, r["threshold"])

    def test_a_table_the_code_does_not_implement_is_refused(self):
        def broken(change):
            tmp = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
            shutil.copytree(layout.RULES, tmp / "rules")
            rows = read_tsv(tmp / "rules" / layout.RULE_TABLE)
            write_tsv(tmp / "rules" / layout.RULE_TABLE, change(rows))
            return tmp / "rules"

        def set_field(rule_id, field, value):
            def change(rows):
                next(r for r in rows if r["rule_id"] == rule_id)[field] = value
                return rows
            return change

        for change in (lambda rows: rows[:-1],                                   # a rule removed
                       set_field("M0_ORF", "missing_policy", "fail"),          # a missing-value policy the code does not apply
                       set_field("M2_MW", "operator", "~"),                    # an unknown operator
                       set_field("M2_SILICA_Z", "routes", "silica; glass"),    # a route that does not exist
                       set_field("M1_EPITOPE", "score_delta", "2"),            # a weighted component
                       set_field("M2_TMH", "rule_id", "M2_MW")):               # a duplicated identifier
            with self.assertRaises(rules.RuleTableError):
                rules.load_rules(broken(change))


class Evaluate(unittest.TestCase):
    def test_boundary_and_equality_cases_from_the_specification(self):
        cases = read_tsv(HERE / "data" / "rule_boundary_cases.tsv")
        self.assertEqual(len(cases), 68)
        self.assertEqual({c["rule_id"] for c in cases}, {r["rule_id"] for r in rules.executable(RULES)})
        for c in cases:
            rule = BY_ID[c["rule_id"]]
            if rule["operator"] == "BETWEEN":
                continue   # the specification tests each bound separately; covered in test_between
            thr, _ = rules.threshold_of(rule, SYMBOL)
            self.assertIs(rules.evaluate(c["input_value"], rule["operator"], thr), c["expected_condition"] == "True", c["test_case_id"])

    def test_one_sided_rules_below_at_above(self):
        want = {"<": (True, False, False), "<=": (True, True, False), ">": (False, False, True), ">=": (False, True, True)}
        n = 0
        for rule in rules.executable(RULES):
            if rule["operator"] not in want:
                continue
            thr, _ = rules.threshold_of(rule, SYMBOL)
            t = float(thr)
            got = tuple(rules.evaluate(v, rule["operator"], thr) for v in (t - 1, t, t + 1))
            self.assertEqual(got, want[rule["operator"]], rule["rule_id"])
            n += 1
        self.assertEqual(n, 16)

    def test_between(self):
        for rid in ("M2_MW", "M2_GRAVY"):
            rule = BY_ID[rid]
            lo, hi = (float(x) for x in rule["threshold"].split(";"))
            got = [rules.evaluate(v, "BETWEEN", rule["threshold"]) for v in (lo - 1, lo, (lo + hi) / 2, hi, hi + 1)]
            self.assertEqual(got, [False, True, True, True, False], rid)

    def test_equality_truth_tables(self):
        equal = [r for r in rules.executable(RULES) if r["operator"] == "=="]
        self.assertEqual(sorted(r["rule_id"] for r in equal), sorted(EQUALITY_TRUTH_TABLES))
        for rule in equal:
            for value, expected in EQUALITY_TRUTH_TABLES[rule["rule_id"]]:
                self.assertIs(rules.evaluate(value, "==", rule["threshold"]), expected, (rule["rule_id"], value))

    def test_a_missing_value_is_not_evaluable(self):
        for rule in rules.executable(RULES):
            thr, _ = rules.threshold_of(rule, SYMBOL)
            for missing in (None, "", " ", "NA", "NaN", "nan", "None", "NULL"):
                self.assertIsNone(rules.evaluate(missing, rule["operator"], thr), (rule["rule_id"], missing))
            if rule["operator"] != "==":
                self.assertIsNone(rules.evaluate("not_a_number", rule["operator"], thr), rule["rule_id"])
                self.assertIsNone(rules.evaluate("-", rule["operator"], thr), rule["rule_id"])


if __name__ == "__main__":
    unittest.main()
