"""Record what each declared output was produced from, at the moment it is written.

The engine computes staleness by comparison, never by judgement: an output with no
<capsule>/.research/produced_from/<logical_id>.yaml is UNRECORDED, which is neither current nor
stale and can never justify a rerun. So every producing script in this capsule calls record_output()
for each table it writes, with the inputs and the code that actually ran.

Importing the engine is deliberate: the hash function, the logical_id rule and the record shape are
the engine's, and a local reimplementation would drift from the verdicts that read it.
"""
import importlib
import os
import sys

# 2026-10-19 patch: the engine location comes from the environment, or is found relative to this
# capsule, instead of naming one machine's path; and the engine module is loaded by name at run time.
# Behaviour is unchanged — with RESEARCHOS_ENGINE set, as in a real run, this resolves exactly as
# before, and a missing engine still yields staleness = None and an UNRECORDED output.
ENGINE = os.environ.get("RESEARCHOS_ENGINE", "")
if not ENGINE:
    _here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):                        # walk up from 02_code/ to a tree holding .researchOS
        _cand = os.path.join(_here, ".researchOS")
        if os.path.isdir(_cand):
            ENGINE = _cand
            break
        _here = os.path.dirname(_here)
_PROD = os.path.join(ENGINE, "production") if ENGINE else ""
if _PROD and _PROD not in sys.path:
    sys.path.insert(0, _PROD)

try:
    staleness = importlib.import_module("staleness")
except Exception as exc:                      # the engine is not importable from here
    staleness = None
    _WHY = f"{type(exc).__name__}: {exc}"
else:
    _WHY = ""


def record_output(capsule, output_path, inputs, code, parameters=None):
    """Write the produced_from record for one output. Returns its path, or None with a printed reason.

    Never raises: provenance recording must not be able to fail a run that already produced correct
    data. A missing record is visible as UNRECORDED in `research_os stale`, which is the honest
    state, whereas a half-written run is not.
    """
    if staleness is None:
        print(f"  provenance NOT recorded for {output_path}: engine not importable ({_WHY})")
        return None
    try:
        p = staleness.record(capsule, output_path, inputs=list(inputs), code=list(code),
                             parameters=parameters)
        return p
    except Exception as exc:
        print(f"  provenance NOT recorded for {output_path}: {type(exc).__name__}: {exc}")
        return None
