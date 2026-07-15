# Design

`GET /api/research/component-catalog?family=ema_pullback` calls `GET /v1/strategies/ema_pullback/composer-catalog`, validates the legacy Workbench DTO, and caches the result for the application lifetime. Research Service owns transport adaptation only; component semantics remain in Strategy Engine.
