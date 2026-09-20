# F1 Historical Data Store

Layered storage. Never collapse layers, never fabricate records.

- `raw/<source>/` — byte-identical provider payloads + sidecar manifests.
- `normalized/` — source records in a common shape (still source-flavoured).
- `canonical/` — entity-resolved, validated records with stable IDs.
- `derived/<dimension>/` — observed/derived/inferred/simulated features.
- `calibration/` — fitted calibration profiles (with uncertainty + method).
- `validation/` — quality reports and conflict records.
- `manifests/` — append-only ingestion manifests + dataset registry.

Rules: missing data is `null` + an availability record; derived values
carry `feature_type`; provenance chains every transformation.
