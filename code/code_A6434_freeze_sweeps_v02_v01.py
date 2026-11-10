#!/usr/bin/env python3
"""Freeze ST_A6434_03_parameter_sweeps_v02.tsv from the pre-execution contract.

Every value is derived from the measurement scale and the M0_ENTRY_REFERENCE predictor
distribution ONLY. No eligibility, pass count, final-pass set or Jaccard is computed here,
which is what prompt §5 requires: cutoffs are frozen before outcomes are seen.
"""
import csv, os, sys, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _provenance import record_output

CAP = sys.argv[1]
CAND = f"{CAP}/04_tables/candidate_data_v02.tsv"
CONTRACT = f"{CAP}/capsule_brain/ST_A6434_03_parameter_sweep_contract_v02.tsv"
OUT = f"{CAP}/01_analysis_output/derived/ST_A6434_03_parameter_sweeps_v02.tsv"

# ---- M0_ENTRY_REFERENCE: one row per pangenome_id, n = 1527 ----
rows = list(csv.DictReader(open(CAND), delimiter="\t"))
ref = {}
for r in rows:
    ref.setdefault(r["pangenome_id"], r)
ref = list(ref.values())
assert len(ref) == 1527, f"reference population is {len(ref)}, expected 1527"

x = np.array([float(r["conservation__median_conservation_hnorm"]) for r in ref
              if r["conservation__median_conservation_hnorm"] not in ("", "NA")])

def kde_reflect(data, bw, grid):
    """Gaussian KDE with reflection at 0 and 1 so the endpoint mass at H.norm = 1 survives."""
    xs = np.concatenate([data, -data, 2 - data])
    dens = np.exp(-0.5 * ((grid[:, None] - xs[None, :]) / bw) ** 2).sum(1)
    return dens / (data.size * bw * np.sqrt(2 * np.pi))

n = x.size
sd = x.std(ddof=1)
iqr = float(np.subtract(*np.percentile(x, [75, 25])))
# Silverman: with a 96.6% plateau the IQR is 0, so the rule falls back to sd by construction.
BW = 0.9 * min(sd, iqr / 1.349 if iqr > 0 else sd) * n ** (-1 / 5)
BW_SCOTT = sd * n ** (-1 / 5)
GRID = np.arange(0, 1.0 + 1e-12, 0.0005)

def antimode(bw):
    d = kde_reflect(x, bw, GRID)
    assert d[-1] > d[-2], "no endpoint mode at H.norm = 1.0"
    minima = [GRID[i] for i in range(1, len(d) - 1) if d[i] <= d[i - 1] and d[i] < d[i + 1]]
    return max(minima)  # nearest density antimode immediately left of the conserved mode

AM = float(antimode(BW))
AM_SCOTT = float(antimode(BW_SCOTT))
UPPER = 1.0                      # endpoint conserved-mode boundary, a valid mode per §5b
WIDTH = UPPER - AM

KDE_NOTE = (f"KDE gaussian w/ boundary reflection, Silverman bw={BW:.6f} (IQR=0 under the "
            f"H.norm=1 plateau so the rule resolves to sd), grid step 0.0005; endpoint mode at "
            f"1.0; nearest antimode to its left {AM:.4f}; Scott bw={BW_SCOTT:.6f} gives "
            f"{AM_SCOTT:.4f} (delta {abs(AM-AM_SCOTT):.4f} on the score axis)")

CONS = {f"HNORM_KDE_F{int(f*100):02d}": (AM + f * WIDTH,
        f"antimode {AM:.4f} + {f:.1f}x(1.0-antimode); {KDE_NOTE}")
        for f in (0.0, 0.2, 0.4, 0.6, 0.8)}

# ---- compact grids from measurement scale, chosen before any eligibility is computed ----
# _01 / _02 are the inner and outer probe of that boundary; LOW / HIGH say which direction
# (for the two-sided MW rule, which boundary moves) — one boundary at a time, per §5d.
GRIDS = {
 "M0_FULL_LENGTH": {
   "FULL_LENGTH_LO_01": ("0.99", "relax the annotation full-length floor by 1% of the ratio scale"),
   "FULL_LENGTH_LO_02": ("0.95", "relax the floor by 5%; min observed ratio 0.7186, p1 0.9978"),
   "FULL_LENGTH_HI_01": ("1.01", "tighten the floor by 1%; ratios above 1 exist (max 1.4676)"),
   "FULL_LENGTH_HI_02": ("1.05", "tighten the floor by 5% on the same ratio scale"),
 },
 "M2_MW": {
   "M2_MW_LOW_02":  ("15000;60000", "lower boundary -5 kDa, upper held canonical; p25 = 21.1 kDa"),
   "M2_MW_LOW_01":  ("25000;60000", "lower boundary +5 kDa, upper held canonical"),
   "M2_MW_HIGH_01": ("20000;50000", "upper boundary -10 kDa, lower held canonical; p75 = 45.8 kDa"),
   "M2_MW_HIGH_02": ("20000;70000", "upper boundary +10 kDa, lower held canonical; p95 = 81.0 kDa"),
 },
 "M2_SILICA_Z": {
   "M2_SILICA_Z_LOW_01":  ("-20", "5-charge-unit step below reference; p5 = -23.06"),
   "M2_SILICA_Z_LOW_02":  ("-25", "10-charge-unit step below reference; p1 = -35.39"),
   "M2_SILICA_Z_HIGH_01": ("-10", "5-charge-unit step above reference; p25 = -9.19"),
   "M2_SILICA_Z_HIGH_02": ("-5",  "10-charge-unit step above reference; median = -2.54"),
 },
 "M2_CELLULOSE_LEN": {
   "M2_CELLULOSE_LEN_LOW_01":  ("300", "100-aa step below reference; median length 279 aa"),
   "M2_CELLULOSE_LEN_LOW_02":  ("200", "200-aa step below reference; p25 = 185 aa"),
   "M2_CELLULOSE_LEN_HIGH_01": ("500", "100-aa step above reference; p75 = 411.75 aa"),
   "M2_CELLULOSE_LEN_HIGH_02": ("600", "200-aa step above reference; p95 = 723.75 aa"),
 },
 "M2_AEX_PI": {
   "M2_AEX_PI_LOW_01":  ("5.5", "0.5 pI unit below reference; p25 = 4.94"),
   "M2_AEX_PI_LOW_02":  ("5.0", "1.0 pI unit below reference; p5 = 4.35"),
   "M2_AEX_PI_HIGH_01": ("6.5", "0.5 pI unit above reference; median pI 6.31"),
   "M2_AEX_PI_HIGH_02": ("7.0", "1.0 pI unit above reference, still below the unassigned 6<pI<8 band top"),
 },
 "M2_CEX_PI": {
   "M2_CEX_PI_LOW_01":  ("7.5", "0.5 pI unit below reference, inside the unassigned band"),
   "M2_CEX_PI_LOW_02":  ("7.0", "1.0 pI unit below reference"),
   "M2_CEX_PI_HIGH_01": ("8.5", "0.5 pI unit above reference; p75 = 9.25"),
   "M2_CEX_PI_HIGH_02": ("9.0", "1.0 pI unit above reference"),
 },
 "M2_CDS_LEN": {
   "M2_CDS_LEN_LOW_01":  ("720", "-120 nt = -40 codons from the resolved median 840"),
   "M2_CDS_LEN_LOW_02":  ("600", "-240 nt = -80 codons; p25 = 558 nt"),
   "M2_CDS_LEN_HIGH_01": ("960", "+120 nt = +40 codons from the resolved median"),
   "M2_CDS_LEN_HIGH_02": ("1080", "+240 nt = +80 codons; p75 = 1237.5 nt"),
 },
}

contract = list(csv.DictReader(open(CONTRACT), delimiter="\t"))
fields = list(contract[0].keys())
filled = unchanged = 0
for r in contract:
    if r["resolution_status"] == "RESOLVED" and r["sweep_value"]:
        unchanged += 1
        continue
    sid, rid = r["sweep_id"], r["rule_id"]
    if r["is_reference"].strip().upper() == "TRUE" and not r["sweep_value"]:
        # the canonical reference row only needs its two-sided value materialised
        r["sweep_value"] = r["reference_value"]
        r["value_source"] = "canonical_reference"
        r["resolution_status"] = "RESOLVED"
        filled += 1
        continue
    if rid == "M0_CONSERVATION" and sid in CONS:
        val, why = CONS[sid]
        r["sweep_value"] = f"{val:.6f}"
        r["derivation_method"] = "KDE conserved-mode antimode; equal score-axis fractions, not member quantiles"
    elif rid in GRIDS and sid in GRIDS[rid]:
        val, why = GRIDS[rid][sid]
        r["sweep_value"] = val
    else:
        raise SystemExit(f"UNHANDLED pending row: {rid} / {sid}")
    r["value_source"] = "frozen_pre_execution_2026-10-06"
    r["predeclared_rationale"] = why
    r["resolution_status"] = "RESOLVED"
    r["reference_population"] = "M0_ENTRY_REFERENCE"
    r["n_reference_population"] = "1527"
    filled += 1

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
    w.writeheader()
    w.writerows(contract)

ids = [(r["rule_id"], r["sweep_id"]) for r in contract]
assert len(ids) == len(set(ids)), "grain violation: rule_id x sweep_id not unique"
assert not [r for r in contract if r["resolution_status"] != "RESOLVED"], "rows still pending"
# the freeze is a produced output like any other: recorded so its staleness is computable
if record_output(CAP, OUT,
                 ["04_tables/candidate_data_v02.tsv",
                  "capsule_brain/ST_A6434_03_parameter_sweep_contract_v02.tsv"],
                 ["02_code/code_A6434_freeze_sweeps_v02_v01.py", "02_code/_provenance.py"]) is None:
    print("WARNING: the frozen sweeps carry no produced_from record; `research_os stale` will "
          "report them UNRECORDED")
else:
    print("provenance: the frozen sweeps carry a produced_from record")
print(f"frozen -> {OUT}")
print(f"rows {len(contract)} | newly resolved {filled} | already resolved {unchanged} | grain rule_id x sweep_id unique")
print(f"conservation antimode {AM:.6f} (Silverman bw {BW:.6f}); Scott {AM_SCOTT:.6f}; interval width {WIDTH:.6f}")
for k in sorted(CONS):
    print(f"  {k} = {CONS[k][0]:.6f}")
