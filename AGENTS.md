# Project rules

- UI copy may be in Russian. All source code, configuration, documentation, and identifiers must be in English and Latin characters.
- The production application must be statically generated and require no API, database, or server-side rendering.
- `docs/election-result.schema.json` is the canonical input contract. Convert external formats in importers; do not add their formats to the UI.
- A low-level source is one JSON file per precinct and ballot. Keep official higher-level protocols as separate canonical files, prefer them in the UI, and sum lower-level files only as a fallback.
- Every import retains the source URL and retrieval timestamp in `source`. Never represent missing data as official results.
- Before committing, run `nix run .#check`, `nix run .#build-index`, and `nix run .#generate`. Do not commit `node_modules`, `.nuxt`, `.output`, or raw downloads.
- Use Nix for development and CI, preferably through `nix run` applications.
- Keep source code in `vibori-analyze/vibori`. The organization Pages repository, `vibori-analyze/vibori-analyze.github.io`, is a separate deployment repository and publishes the generated artifact at `https://vibori-analyze.github.io/`.
- Do not add generated site files to this repository. The Pages repository workflow checks out `master`, runs the required Nix commands, and deploys via GitHub Pages; trigger **Build and deploy** there when an immediate publication is needed.
