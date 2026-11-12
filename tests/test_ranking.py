"""Applying the rules: final pass and additive score on constructed candidates, with the real rule table."""
import itertools
import unittest

from siku01_prioritization import layout, perturbation, ranking, rules

RULES, SYMBOL = rules.load_rules()


def satisfying(rule):
    thr, _ = rules.threshold_of(rule, SYMBOL)
    op = rule["operator"]
    if op == "==":
        return str(thr)
    if op == "BETWEEN":
        lo, hi = (float(x) for x in str(thr).split(";"))
        return str((lo + hi) / 2)
    return str(float(thr) + (1 if op in (">", ">=") else -1))


def violating(rule):
    thr, _ = rules.threshold_of(rule, SYMBOL)
    op = rule["operator"]
    if op == "==":
        return {"single": "multiple", "yes": "no", "1": "0", "0": "1"}[str(thr)]
    if op == "BETWEEN":
        return str(float(str(thr).split(";")[1]) + 1)
    return str(float(thr) - (1 if op in (">", ">=") else -1))


def rules_of(route, role):
    return [r for r in rules.executable(RULES) if r["role"] == role and route in rules.routes_of(r, layout.ROUTES)]


def candidate(route, **changes):
    """A candidate that satisfies every rule of its route, with some variables replaced."""
    row = {"pangenome_id": "1", "route": route}
    for r in rules_of(route, "hard") + rules_of(route, "additive"):
        row[r["variable"]] = satisfying(r)
    row.update(changes)
    return row


def state_of(row):
    # every route must be present for the route list; add a neutral candidate on the other routes
    frame = [row] + [candidate(rt) | {"pangenome_id": "2"} for rt in layout.ROUTES if rt != row["route"]]
    _, states, _ = ranking.apply_rules(RULES, SYMBOL, frame)
    return states[0]


class FinalPass(unittest.TestCase):
    def test_all_gates_satisfied_is_pass_with_full_score(self):
        for route in layout.ROUTES:
            s = state_of(candidate(route))
            self.assertEqual(s["final_pass"], "PASS", route)
            self.assertEqual(s["n_hard_applicable"], len(rules_of(route, "hard")))
            self.assertEqual(s["additive_score"], len(rules_of(route, "additive")))

    def test_one_failing_gate_is_fail(self):
        for route in layout.ROUTES:
            for gate in rules_of(route, "hard"):
                s = state_of(candidate(route, **{gate["variable"]: violating(gate)}))
                self.assertEqual((s["final_pass"], s["n_hard_fail"]), ("FAIL", 1), (route, gate["rule_id"]))

    def test_one_missing_gate_value_is_not_evaluable(self):
        for route in layout.ROUTES:
            for gate in rules_of(route, "hard"):
                s = state_of(candidate(route, **{gate["variable"]: ""}))
                self.assertEqual((s["final_pass"], s["n_hard_not_evaluable"]), ("NOT_EVALUABLE", 1), (route, gate["rule_id"]))

    def test_fail_outranks_not_evaluable(self):
        gates = rules_of("silica", "hard")
        s = state_of(candidate("silica", **{gates[0]["variable"]: violating(gates[0]), gates[-1]["variable"]: ""}))
        self.assertEqual(s["final_pass"], "FAIL")
        self.assertEqual(ranking.final_pass_of(["PASS", "NOT_EVALUABLE", "FAIL"]), "FAIL")
        self.assertEqual(ranking.final_pass_of(["PASS", "NOT_EVALUABLE"]), "NOT_EVALUABLE")
        self.assertEqual(ranking.final_pass_of([]), "PASS")

    def test_a_gate_of_another_route_does_not_apply(self):
        # a protein too long for cellulose and too little charged for silica still passes anion exchange
        s = state_of(candidate("aex", rep__protein_length_aa="5000", rep__charge_pH_7_0="0"))
        self.assertEqual(s["final_pass"], "PASS")


class AdditiveScore(unittest.TestCase):
    def test_score_is_the_number_of_satisfied_components(self):
        n = 0
        for route in layout.ROUTES:
            components = rules_of(route, "additive")
            for satisfied in itertools.product([True, False], repeat=len(components)):
                row = candidate(route, **{c["variable"]: (satisfying(c) if ok else violating(c)) for c, ok in zip(components, satisfied)})
                s = state_of(row)
                self.assertEqual(s["additive_score"], sum(satisfied), (route, satisfied))
                self.assertEqual(s["final_pass"], "PASS", "an additive component must never change eligibility")
                n += 1
        self.assertEqual(n, 4 * 2 ** 5 + 2 * 2 ** 4)

    def test_a_missing_component_adds_zero(self):
        for route in layout.ROUTES:
            for c in rules_of(route, "additive"):
                s = state_of(candidate(route, **{c["variable"]: "NA"}))
                self.assertEqual(s["additive_score"], len(rules_of(route, "additive")) - 1, (route, c["rule_id"]))
                self.assertEqual(s["final_pass"], "PASS")


class LeaveOneOut(unittest.TestCase):
    HARD, ADD = {"H1", "H2", "H3"}, {"A1", "A2", "A3"}

    def test_final_pass_with_one_gate_omitted(self):
        P, F, N = "PASS", "FAIL", "NOT_EVALUABLE"
        cases = [({"H1": P, "H2": P, "H3": P}, None, P), ({"H1": P, "H2": F, "H3": P}, None, F),
                 ({"H1": P, "H2": N, "H3": P}, None, N), ({"H1": F, "H2": N, "H3": P}, None, F), ({}, None, P),
                 ({"H1": P, "H2": F, "H3": P}, "H2", P),    # removing the only failing gate admits
                 ({"H1": P, "H2": F, "H3": P}, "H1", F),    # removing a passing gate changes nothing
                 ({"H1": F, "H2": F, "H3": P}, "H1", F),    # a second failing gate still fails
                 ({"H1": N, "H2": P, "H3": P}, "H1", P),    # removing the gate that could not be evaluated admits
                 ({"H1": P, "A1": "0", "A2": "+1"}, None, P)]   # additive outcomes are not gates
        for d, omit, want in cases:
            self.assertEqual(perturbation.final_pass(d, self.HARD, omit), want, (d, omit))

    def test_score_with_one_component_omitted(self):
        cases = [({"A1": "+1", "A2": "+1", "A3": "+1"}, None, 3), ({"A1": "+1", "A2": "0", "A3": "+1"}, None, 2),
                 ({"A1": "+1", "A2": "+1", "A3": "+1"}, "A2", 2), ({"A1": "+1", "A2": "0", "A3": "+1"}, "A2", 2),
                 ({"A1": "+1", "H1": "PASS"}, None, 1), ({}, None, 0)]
        for d, omit, want in cases:
            self.assertEqual(perturbation.score(d, self.ADD, omit), want, (d, omit))

    def test_spearman(self):
        self.assertAlmostEqual(perturbation.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(perturbation.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertAlmostEqual(perturbation.spearman([1, 2, 2, 3], [1, 2, 2, 3]), 1.0)   # ties get average ranks
        self.assertIsNone(perturbation.spearman([1, 1, 1], [1, 2, 3]))                   # undefined when one side is constant


if __name__ == "__main__":
    unittest.main()
