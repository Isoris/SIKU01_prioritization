"""SIKU01 candidate prioritization: 23 rules, six production routes, 1,527 core orthogroups.

Modules, in the order a run uses them:

    layout        where things are in the repository, the six routes, the output file names
    tables        reading and writing tab-separated files, checksums
    inputs        check the frozen input tables, build the literature table, assemble one row per orthogroup
    rules         load and validate the rule table; the one comparison function every step uses
    ranking       apply the 22 executable rules to every orthogroup on every route
    sweeps        sensitivity: move one threshold at a time
    perturbation  sensitivity: leave one hard gate out, leave one additive component out
    shortlists    reader-friendly views: final-pass candidates per route
    verify        compare a run with the deposited tables; independent recomputation
    pipeline      runs the steps above in order
    cli           the command line (python prioritize.py ...)
"""
__version__ = "2.0.0"
