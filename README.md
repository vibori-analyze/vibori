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

`nix run .#generate public` creates a `./public` symlink to the generated static site for GitHub Pages. It runs the locked `npm ci` inside a Nix environment. `nix develop` is only needed for interactive UI development.

Publish `.output/public` for GitHub Pages. Set `NUXT_APP_BASE_URL=/repository-name/` before building when the project is hosted below the domain root.

## Data

The only service input format is [docs/election-result.schema.json](docs/election-result.schema.json). Store each precinct file at `public/data/<election-id>/precincts/*.json` and official higher-level protocols at `public/data/<election-id>/aggregates/*.json`. Both use exactly the same contract. `scripts/build-index.mjs` produces `public/data/index.json` and derives territorial commissions and regions from `administrative_path`.

Candidate and party identifiers must remain stable across files so their pages can aggregate all elections. For every requested unit, the UI first loads its indexed official protocol. If it is absent, the UI sums matching lower-level precinct files and labels the result as calculated.

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
