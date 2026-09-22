# Vibori

A static election-results viewer. Nuxt generates the application and the browser reads only JSON from `public/data`. Official higher-level protocols are preferred when available; otherwise the browser computes the result from lower-level protocols. The site can therefore be published on GitHub Pages without a server or database.

The UI follows the precinct → territorial commission → region → country hierarchy. It provides result tables, turnout, vote-share charts, and cross-election candidate and party pages.

```bash
nix run .#import-izbirkom -- --election-id 587813923 --max-precincts 1 --dry-run
nix run .#import-izbirkom                 # import every accessible election
nix run .#build-index                     # build precinct/commission/region catalog
nix run .#check                           # Python lint/types and TypeScript types
nix run .#generate                        # static site: ./dist
```

`nix run .#generate` creates a `./dist` symlink to the generated static site. It runs the locked `npm ci` inside a Nix environment. `nix develop` is only needed for interactive UI development. Do not use the source `public` directory as the generation target.

Publish `.output/public` for GitHub Pages. Set `NUXT_APP_BASE_URL=/repository-name/` before building when the project is hosted below the domain root.

## Deployment

The source lives in `vibori-analyze/vibori`. The separate `vibori-analyze/vibori-analyze.github.io` repository builds it and publishes the generated site at <https://vibori-analyze.github.io/>. Its workflow checks for source updates every hour and can also be run manually.

Run the **Build and deploy** workflow in the Pages repository when a rebuild is needed immediately.

## Data

The only service input format is [docs/election-result.schema.json](docs/election-result.schema.json). Store each precinct file at `public/data/<election-id>/precincts/*.json` and official higher-level protocols at `public/data/<election-id>/aggregates/*.json`. Both use exactly the same contract. `scripts/build-index.mjs` produces `public/data/index.json` and derives territorial commissions and regions from `administrative_path`.

Candidate and party identifiers must remain stable across files so their pages can aggregate all elections. For every requested unit, the UI first loads its indexed official protocol. If it is absent, the UI sums matching lower-level precinct files and labels the result as calculated.

## Performance and generated data

The home page loads only the small election catalog and the current commission branch. Search covers the current list, including every precinct page of the selected territorial commission. Rendering is limited to 48 cards per page. Candidate tables use search and 25 rows per page. Election and commission navigation are stored in the URL and work with browser history. Fonts are local system fonts; links do not prefetch result pages.

The indexer reads canonical protocols in ordered batches of 32 and reuses a numeric collator. Computed totals contain only entities actually present in their constituent protocols, including reported zero votes. Official protocols and source provenance are unchanged.

Chart analysis v3 stores lossless numeric precinct tuples once per national or regional segment. Shares and histograms are derived for the selected commission and active entities when its chart is opened. The reader also supports existing v2 indexes. Large chart data uses shallow reactivity, and scatter hover lookup uses screen cells instead of scanning the entire archive on every mouse move.

To rebuild without changing existing generated files, supply a separate output directory:

```bash
nix run .#build-index -- public/data /tmp/vibori-index
VIBORI_INDEX_DIR=/tmp/vibori-index nix run .#generate
```

The output directory contains derived files only. Generation copies the canonical archive and overlays these indexes. Do not publish the index directory alone. The default build command still rebuilds in `public/data` for the deployment workflow.

`nix run .#check` includes offline regression tests for pagination beyond 500 precincts, official-total precedence, unchanged source files, exact chart values, and incomplete import rejection. Imports share a worker pool per election, cache repeated entity identifiers, and atomically replace completed JSON files so interrupted writes cannot be mistaken for completed downloads.

## izbirkom.ru import

The [config/izbirkom.json](config/izbirkom.json) configuration defines the official SPA API endpoint, timeouts, retries, and optional proxy. The importer reads the complete election catalog, walks each available commission tree, downloads report 242 for precincts and every higher level, and converts each available ballot into the canonical v1 format. URL and retrieval time remain in `source`. Existing files are skipped, so an interrupted import can be resumed with the same command.

Direct access is the default and needs no setup:

```bash
nix run .#import-izbirkom
```

HTTP(S) and SOCKS5 proxies remain available when needed. Set `VIBORI_PROXY` in the ignored `.env` file, pass `--proxy http://localhost:8080`, or use `--no-proxy` to override both environment and configuration. Priority is `--no-proxy` → `--proxy` → `VIBORI_PROXY` → config. The `start` event reports only the proxy host, never its credentials.

```bash
nix run .#import-izbirkom -- --date-from 2026-01-01 --date-to 2026-12-31
nix run .#import-izbirkom -- --election-id 587813923
nix run .#import-izbirkom -- --proxy socks5h://127.0.0.1:1080
nix run .#build-index
```

For a small connectivity check, use `--election-id 587813923 --max-precincts 1 --dry-run`. `--workers` controls concurrent report requests and `--progress-every` controls tree progress frequency. The importer emits JSON Lines events including `election_page`, `election`, `tree_progress`, `protocol`, `protocol_unavailable`, errors, and `complete`. A missing higher-level protocol is recorded as unavailable and activates the UI fallback; other API failures remain errors. Missing data is never represented as an official result.
