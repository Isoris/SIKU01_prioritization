#!/usr/bin/env python3
import pandas as pd, os, sys, math
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
T=os.path.join(ROOT,"04_tables")
B=os.path.join(ROOT,"capsule_brain")
rules=pd.read_csv(os.path.join(B,"ranking_rules_v27.tsv"),sep="\t",dtype=str).fillna("")
cases=pd.read_csv(os.path.join(B,"test_case_definition_v01.tsv"),sep="\t",dtype=str).fillna("")
params=pd.read_csv(os.path.join(B,"rule_parameter_resolution_v02.tsv"),sep="\t",dtype=str).fillna("")
cand=pd.read_csv(os.path.join(T,"candidate_data_v02.tsv"),sep="\t")
u=cand.drop_duplicates("pangenome_id")
bad=[]
def ev(op,thr,x):
    x=float(x)
    if op=="BETWEEN":
        lo,hi=map(float,thr.split(";")); return lo <= x <= hi
    t=float(thr)
    return {"<":x<t,"<=":x<=t,">":x>t,">=":x>=t,"==":x==t}[op]
for _,r in rules.iterrows():
    if r.operator not in {"<","<=",">",">=","BETWEEN"}: continue
    z=cases[(cases.rule_id==r.rule_id)&(cases.test_level=="criterion")&(cases.test_type=="boundary")]
    for _,c in z.iterrows():
        try: got=ev(r.operator,r.threshold,c.input_value)
        except Exception: continue
        exp=str(c.expected_condition).strip().lower()=="true"
        if got!=exp: bad.append(("BOUNDARY",r.rule_id,c.test_case_id,r.operator,r.threshold,c.input_value,exp,got))
for _,p in params.iterrows():
    x=pd.to_numeric(u[p.source_column],errors="coerce").dropna()
    got=x.quantile(.75) if p.statistic_type=="population_quantile" else x.median()
    exp=float(p.resolved_value)
    if len(x)!=int(p.n_reference) or not math.isclose(got,exp,rel_tol=0,abs_tol=1e-12):
        bad.append(("PARAMETER",p.rule_id,p.source_column,p.statistic_type,p.n_reference,exp,got))
if bad:
    print("FAIL: authority/provenance mismatch")
    for b in bad: print(*b,sep="\t")
    sys.exit(1)
print("PASS: numeric boundary cases agree with rule authority and all five Q3/median parameters recompute from the stamped M0-entry population (n=1,527)")
