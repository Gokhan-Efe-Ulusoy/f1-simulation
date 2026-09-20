# Data Licensing & Usage

No source data is bundled in this repository. The directories under
`data/raw/` ship with `.gitkeep` placeholders only.

- **Jolpica (Ergast-compatible)**: free public API, no key, CC BY-SA
  heritage via Ergast; respect provider rate limits and terms at
  https://api.jolpi.ca/ergast/f1 and https://github.com/jolpica/jolpica-f1.
- **OpenF1**: https://www.openf1.org — live timing/session data, 2018+;
  respect rate limits.
- **FastF1**: MIT (https://github.com/theOehrly/Fast-F1); requires its own
  install and local cache; user-managed downloads.
- **Kaggle**: dataset-specific licenses (check each dataset page for
  owner/slug/license); `KaggleSourceAdapter` records owner/slug/version/
  hash for traceability but does not redistribute datasets.
- **GitHub**: repository-specific licenses; pin to commit SHA or
  immutable release; do not ingest code as data.
- **FIA / Formula 1 Official**: all rights reserved; curated document
  imports are marked `provider="curated"` and must not be presented as
  observed source records. Check official terms before redistribution.
- **Weather providers**: licensing must be reviewed per provider before
  production use; observations land in `HistoricalWeatherObservation`
  with explicit units.

Provenance (`DataProvenance`) records provider, URL, retrieval time,
parser version and raw sha256 for every imported record. The repository
contains metadata, schemas, manifests and download instructions — never
copyrighted datasets when redistribution is not permitted.
