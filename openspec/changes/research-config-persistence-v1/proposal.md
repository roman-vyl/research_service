# Proposal: Research config persistence v1

Restore the preserved Workbench config save/list/select surface in the independent Research Service.
Research owns durable draft state. Strategy Engine remains the sole semantic validator for strategy
instances. No production code imports or executes `legacy_source`.
