"""The command line: the read-only commands answer, and a wrong request ends with a non-zero exit code."""
import contextlib
import io
import unittest

from siku01_prioritization import cli


def call(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:   # argparse exits by itself on a wrong argument
            code = e.code
    return code, out.getvalue()


class CommandLine(unittest.TestCase):
    def test_rules(self):
        code, out = call("rules")
        self.assertEqual(code, 0)
        self.assertEqual(sum(line.startswith("M") for line in out.splitlines()), 23)
        code, out = call("rules", "--route", "silica")
        self.assertIn("M2_SILICA_Z", out)
        self.assertNotIn("M2_CEX_PI", out)

    def test_check_inputs(self):
        code, out = call("check-inputs")
        self.assertEqual(code, 0)
        self.assertIn("13 of 13 frozen tables", out)

    def test_show(self):
        for query in ("21", "polC", "SIKU01_000318"):
            code, out = call("show", query)
            self.assertEqual(code, 0, query)
            self.assertIn("pangenome_id 21 ", out)
            self.assertIn("M2_MW             FAIL", out)
        self.assertEqual(call("show", "no_such_gene")[0], 1)

    def test_shortlist(self):
        code, out = call("shortlist", "silica", "-n", "0")
        self.assertEqual(code, 0)
        self.assertIn("silica: 85 final-pass candidates", out)
        self.assertEqual(sum("SIKU01_" in line for line in out.splitlines()), 85)
        self.assertNotEqual(call("shortlist", "glass")[0], 0)

    def test_verify_the_deposited_tables(self):
        code, out = call("verify", "expected")
        self.assertEqual(code, 0)
        self.assertIn("21 of 21", out)
        self.assertIn("9162 candidates recomputed by separate code, 0 differ", out)

    def test_no_command_prints_help(self):
        code, out = call()
        self.assertEqual(code, 2)
        self.assertIn("reproduce", out)


if __name__ == "__main__":
    unittest.main()
