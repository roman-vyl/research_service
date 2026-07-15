# Design

A position that existed at bar open is evaluated against the current MDS candle. Initial stop and take levels come from the immutable `InitialProtection`; signal exits come from Strategy Engine `exit_policy.signal_exit`.

Distance exits preserve BBB/vectorbt semantics: a gap through a level fills at bar open, otherwise an intrabar touch fills at the level. Signal exits fill at bar close. The entry bar is not eligible for exit because the legacy managed loop opened only after bar-open exit processing.

Same-bar policy `v1` orders static candidates as stop loss, take profit, then signal. The result preserves losing candidates for later attribution and diagnostics. Managed candidates are intentionally deferred to the unified arbitration slice.
