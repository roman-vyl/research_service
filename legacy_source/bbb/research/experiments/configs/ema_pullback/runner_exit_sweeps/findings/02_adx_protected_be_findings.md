# ADX protected + BE findings

## Purpose

We tested whether ADX/DI can move trades into a protected phase and whether break-even stop should protect the entry after ADX impulse confirmation.

## Main conclusion

Naive hard BE at entry is not accepted as a universal protective rule.

More precise interpretation:

```text
ADX/DI is useful.
Hard BE at entry is too crude.
```

## What worked

ADX/DI direction audit showed no direction errors in checked full reports:

```text
long runner/protected condition:  +DI > -DI
short runner/protected condition: -DI > +DI
```

ADX/DI selected a high-quality subset of trades.

## What failed

The action attached to protected was wrong:

```text
phase -> protected
protected -> hard stop at entry
```

Many BE exits occurred after large MFE had already happened. This means the rule often converted a proven impulse into a near-zero / fee-loss exit instead of capturing the move.

## Rejected interpretation

Do not conclude:

```text
BE works only on strict, not relaxed.
```

That is overfitting. A protective rule should have a universal formula. The current hard-BE formula has not earned that status.

## Better interpretation

```text
Strict entries survive crude BE better because entry quality is higher.
Relaxed entries reveal the weakness of crude BE faster.
The formula is the problem, not necessarily the idea of protection.
```

## Follow-up ideas

Possible later protective variants:

```text
1. buffered BE: entry + fees / 0.1 ATR / 0.2 ATR
2. close-confirmed failure exit: close beyond BE for N bars
3. lock-profit stop after runner instead of entry BE
4. phase rule requiring ADX rising / DI spread expansion instead of static ADX threshold
```

Do not prioritize these before the runner/RSI fee rerun. Current data suggests ADX/DI is more valuable as runner activation than as BE activation.
