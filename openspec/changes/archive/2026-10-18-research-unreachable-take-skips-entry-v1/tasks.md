## 1. Implementation

- [x] 1.1 `UnreachableTakeProfit` in `execution/protection.py`, raised by both resolvers for the initial take.
- [x] 1.2 `try_open_position` and `try_open_projection_position` return `None` on it.

## 2. Tests

- [x] 2.1 Resolver raises the distinct error; unreachable stop stays a plain `InvalidRequest`.
- [x] 2.2 Both entry functions skip the entry.
