"""End to end: one run from the frozen inputs, compared with the deposited tables, and the views checked against the tables.

The run takes about half a minute and is made once for this whole file.
"""
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from siku01_prioritization import inputs, layout, pipeline, rules, verify
from siku01_prioritization.tables import read_tsv

FINAL_PASS = {"silica": 85, "cellulose": 515, "aex": 387, "cex": 118, "pdna_tilapia": 363, "pdna_zebrafish": 363}
RUN = None


def setUpModule():
    global RUN
    RUN = Path(tempfile.mkdtemp(prefix="siku01_test_run_")) / "run"
    pipeline.run(RUN, say=lambda *_: None)


def tearDownModule():
    shutil.rmtree(RUN.parent, ignore_errors=True)


class Inputs(unittest.TestCase):
    def test_checksums(self):
        rows, problems = inputs.check_inputs()
        self.assertEqual(problems, [])
        self.assertEqual(sum(r["role"] == "frozen_table" for r in rows), 13)

    def test_every_table_the_code_reads_is_listed_as_read(self):
        listed = {r["file"] for r in read_tsv(layout.INPUTS / "CHECKSUMS.tsv") if r["read_by_ranking"] == "yes"}
        read = {spec["path"] for name, spec in inputs.LAYERS.items() if name != "literature"} | {inputs.GENE_COPIES} | {
            "MAP_A5093_locus_pangenome_v02.tsv", "ST_A6035_02_protein_literature_assignments_v01.tsv",
            "ST_A6035_03_vaccine_antigen_crossref_v01.tsv"}
        self.assertEqual(listed, read)

    def test_split_gene_calls_are_the_core_orthogroups_with_two_siku01_calls(self):
        calls = {}
        for r in read_tsv(layout.INPUTS / "MAP_A5093_locus_pangenome_v02.tsv"):
            if r["sample_id"] == "SIKU01" and r["prokka_locus_tag"] and r["pangenome_id"]:
                calls.setdefault(r["pangenome_id"], set()).add(r["prokka_locus_tag"])
        core = {r["pangenome_id"] for r in read_tsv(layout.INPUTS / "protein_descriptors_by_pangenome_id_v01.tsv")
                if r["pangenome_class"] == "core"}
        twice = sorted((p for p, s in calls.items() if len(s) > 1 and p in core), key=int)
        self.assertEqual(twice, inputs.SPLIT_CALL_FAMILIES)
        self.assertEqual(len(core) - len(twice), layout.N_REFERENCE)


class Reproduction(unittest.TestCase):
    def test_21_tables_identical_to_the_deposited_ones(self):
        same, n, problems = verify.compare_with_expected(RUN / "tables")
        self.assertEqual(problems, [])
        self.assertEqual((same, n), (21, 21))

    def test_independent_recomputation(self):
        r = verify.independent_recompute(RUN / "tables")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["rows"], r["differ"], r["thresholds_equal"]), (9162, 0, 5))

    def test_the_independent_recomputation_detects_a_changed_result(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for name in (layout.T_RANKING_INPUTS, layout.T_STATE):
            shutil.copy(RUN / "tables" / name, tmp / name)
        text = (tmp / layout.T_STATE).read_text(encoding="utf-8")
        first = text.split("\n")[1]
        (tmp / layout.T_STATE).write_text(text.replace(first, first.replace("FAIL", "PASS"), 1), encoding="utf-8", newline="\n")
        self.assertIn("FAIL", first)
        r = verify.independent_recompute(tmp)
        self.assertFalse(r["ok"])
        self.assertEqual(r["differ"], 1)

    def test_final_pass_per_route(self):
        states = read_tsv(RUN / "tables" / layout.T_STATE)
        got = Counter(s["route"] for s in states if s["final_pass"] == "PASS")
        self.assertEqual(dict(got), FINAL_PASS)
        self.assertEqual(len(states), 9162)

    def test_frame_equals_the_deposited_candidate_frame(self):
        """The deposit holds the candidate frame as a file (candidate_data_v02.tsv). Here it is built from the input tables; the two
        must agree in row order and in every column they share."""
        deposited = read_tsv(layout.EXPECTED_FRAME)
        built = inputs.build_frame(RUN / "tables" / layout.T_RANKING_INPUTS)
        self.assertEqual([(r["pangenome_id"], r["route"]) for r in deposited], [(r["pangenome_id"], r["route"]) for r in built])
        shared = [c for c in deposited[0] if c in built[0]]
        only_deposited = sorted(c for c in deposited[0] if c not in built[0])
        # the route labels, and three scores of an earlier rule set that no current rule reads
        self.assertEqual(only_deposited, ["candidate_id", "route_id", "score_m1_general", "score_m1_protein", "score_m2_pdna"])
        self.assertEqual(len(shared), 64)
        differing = Counter(c for d, b in zip(deposited, built) for c in shared if d[c] != b[c])
        self.assertEqual(differing, Counter())
        variables = {r["variable"] for r in rules.executable(rules.load_rules()[0])}
        self.assertTrue(variables <= set(shared))

    def test_reference_sweep_row_reproduces_the_gate(self):
        """At the reference threshold a sweep must count exactly the candidates that pass the gate itself."""
        counts = {(c["rule_id"], c["route"]): c for c in read_tsv(RUN / "tables" / layout.T_COUNTS)}
        n = 0
        for s in read_tsv(RUN / "tables" / layout.T_SWEEP_EXECUTION):
            if s["is_reference"] != "TRUE":
                continue
            route = layout.ROUTES[0] if s["population"] == layout.REFERENCE_POPULATION else s["population"]
            self.assertEqual(s["n_satisfying"], counts[(s["rule_id"], route)]["n_pass"], (s["rule_id"], s["population"]))
            self.assertEqual(s["jaccard_vs_reference"], "1.0")
            n += 1
        self.assertEqual(n, 16)


class Views(unittest.TestCase):
    """shortlists/ and routes/ only rearrange the result tables; they must say the same thing."""

    def test_shortlists_match_the_state_table(self):
        states = {(s["pangenome_id"], s["route"]): s for s in read_tsv(RUN / "tables" / layout.T_STATE)}
        for route, n in FINAL_PASS.items():
            short = read_tsv(RUN / "shortlists" / f"final_pass_{route}.tsv")
            self.assertEqual(len(short), n, route)
            self.assertEqual({r["pangenome_id"] for r in short},
                             {p for (p, rt), s in states.items() if rt == route and s["final_pass"] == "PASS"})
            scores = [int(r["additive_score"]) for r in short]
            self.assertEqual(scores, sorted(scores, reverse=True))
            for r in short:
                self.assertEqual(r["additive_score"], states[(r["pangenome_id"], route)]["additive_score"])
        summary = {r["route"]: r for r in read_tsv(RUN / "shortlists" / "final_pass_summary.tsv")}
        self.assertEqual({k: int(v["n_final_pass"]) for k, v in summary.items()}, FINAL_PASS)

    def test_route_folders_match_the_tables(self):
        states = {(s["pangenome_id"], s["route"]): s for s in read_tsv(RUN / "tables" / layout.T_STATE)}
        outcomes = {(o["pangenome_id"], o["route"], o["rule_id"]): o for o in read_tsv(RUN / "tables" / layout.T_OUTCOMES)}
        for route in layout.ROUTES:
            cand = read_tsv(RUN / "routes" / route / "candidates.tsv")
            self.assertEqual(len(cand), layout.N_REFERENCE)
            gates = read_tsv(RUN / "routes" / route / "gates.tsv")
            comps = read_tsv(RUN / "routes" / route / "additive_components.tsv")
            for r in cand:
                s = states[(r["pangenome_id"], route)]
                self.assertEqual((r["final_pass"], r["additive_score"]), (s["final_pass"], s["additive_score"]))
                for g in gates + comps:
                    o = outcomes[(r["pangenome_id"], route, g["rule_id"])]
                    self.assertEqual((r[g["rule_id"]], r[g["variable"]]), (o["outcome"], o["observed_value"]))
                failed = [g["rule_id"] for g in gates if r[g["rule_id"]] == "FAIL"]
                self.assertEqual(r["failed_gates"], "; ".join(failed))
                self.assertEqual(r["final_pass"] == "PASS", all(r[g["rule_id"]] == "PASS" for g in gates))
            for g in gates:
                self.assertEqual(int(g["n_pass"]), sum(r[g["rule_id"]] == "PASS" for r in cand))
            self.assertEqual(int(gates[-1]["funnel_n_pass"]), FINAL_PASS[route])   # the funnel ends at the final-pass count

    def test_all_routes_overview(self):
        rows = read_tsv(RUN / "shortlists" / "final_pass_all_routes.tsv")
        for route, n in FINAL_PASS.items():
            self.assertEqual(sum(r[f"final_pass_{route}"] == "PASS" for r in rows), n)
        self.assertTrue(all(int(r["n_routes_final_pass"]) >= 1 for r in rows))
        self.assertEqual(sum(int(r["n_routes_final_pass"]) for r in rows), sum(FINAL_PASS.values()))


if __name__ == "__main__":
    unittest.main()
