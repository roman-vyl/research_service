# Design

`ProjectRunDiagnostics` reads a validated immutable run bundle through `ReadResearchRuns`.

It slices the stored Strategy Engine evaluation on the requested half-open window, maps component evidence to dense long/short lanes, projects Strategy component masks and Research execution events to sparse `ComponentEvent` records, and optionally exposes a selected HTF context overlay.

The chart-events response is a display-only sparse projection of the same signal trace. No downstream service calls occur during reads.
