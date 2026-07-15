# Specification

Research Service SHALL expose published run artifacts through `/api/research/runs*` without reading or executing legacy BBB result code. Lists SHALL sort by manifest creation time descending. Missing runs SHALL return 404. Invalid versioned artifacts SHALL return a stable server error. Trades and metrics SHALL be direct projections of the persisted authoritative result.
