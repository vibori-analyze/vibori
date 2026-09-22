# Project rules

- UI copy may be in Russian. All source code, configuration, documentation, and identifiers must be in English and Latin characters.
- The production application must be statically generated and require no API, database, or server-side rendering.
- `docs/election-result.schema.json` is the canonical input contract. Convert external formats in importers; do not add their formats to the UI.
- A low-level source is one JSON file per precinct and ballot. Higher-level results are sums of those files.
- Every import retains the source URL and retrieval timestamp in `source`. Never represent missing data as official results.
- Before committing, run available checks. Do not commit `node_modules`, `.nuxt`, `.output`, or raw downloads.
- Use Nix for development and CI, preferably through `nix run` applications.
