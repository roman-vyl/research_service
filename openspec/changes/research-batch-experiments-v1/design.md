# Design

`RunBatchExperiment` loops over immutable candidate requests and delegates each item to
`RunSingleInstanceBacktest` plus `PersistSingleInstanceBacktest`. Exceptions are converted into a
failed candidate result so the next candidate runs. `PersistBatchExperiment` atomically publishes
request, summary, and manifest under the artifact store's `batches` namespace.
