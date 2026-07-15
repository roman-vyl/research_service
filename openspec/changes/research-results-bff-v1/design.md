# Design

A transport-neutral `ReadResearchRuns` use case reads through `RunArtifactReader`. The filesystem adapter lists only published directories containing `manifest.json`. BFF projections are versioned and never depend on the legacy BBB results directory.
