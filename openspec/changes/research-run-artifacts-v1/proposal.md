# Proposal: Research Run Artifacts v1

Persist every completed single-instance backtest as an immutable, versioned and atomically published run directory under `var/runs/<run_id>/`.

This change does not expose HTTP endpoints and does not execute legacy BBB code.
