# Design

The slice preserves the legacy managed-loop entry invariants: long is checked before short, entry is anchored to the signal bar close, and an existing open position blocks re-entry. Research Service owns execution assumptions such as adverse side-aware slippage. Fees, exits and PnL are deferred.
