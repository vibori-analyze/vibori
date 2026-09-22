# Vibori

A static election-results viewer. Nuxt generates the application, the browser reads only JSON from `public/data`, and computes aggregate levels locally. It can therefore be published on GitHub Pages without a server or database.

The UI follows the precinct → territorial commission → region → country hierarchy. It provides result tables, turnout, vote-share charts, and cross-election candidate and party pages.

```bash
nix run .#import-izbirkom -- --dry-run --max-pages 100
nix run .#import-izbirkom                 # import all accessible campaigns
nix run .#build-index                     # build precinct/commission/region catalog
nix run .#generate                        # static site: ./dist
```

`nix run .#generate public` creates a `./public` symlink to the generated static site for GitHub Pages. It runs the locked `npm ci` inside a Nix environment. `nix develop` is only needed for interactive UI development.

Publish `.output/public` for GitHub Pages. Set `NUXT_APP_BASE_URL=/repository-name/` before building when the project is hosted below the domain root.

## Data

The only service input format is [docs/election-result.schema.json](docs/election-result.schema.json). Store each precinct file at `public/data/<election-id>/precincts/*.json`. `scripts/build-index.mjs` produces `public/data/index.json` and derives territorial commissions and regions from `administrative_path`.

Candidate and party identifiers must remain stable across files so their pages can aggregate all elections. Region and commission results are computed in the browser from precinct-level data; no separate aggregates are needed.

## izbirkom.ru import

The [config/izbirkom.json](config/izbirkom.json) configuration defines the official entry point, request rate, retries, crawl limit, and protocol-table signatures. The importer recursively discovers accessible campaigns (including `vrn` links), caches every response in `raw/izbirkom`, and creates v1 files only for recognised precinct protocols. URL and retrieval time remain in `source`.

The importer supports HTTP(S) and SOCKS5 proxy URLs. `.env` is loaded automatically and is ignored by Git. The included local value routes traffic through an SSH SOCKS tunnel on `rus.sixty9.ru`:

```bash
ssh -N -D 127.0.0.1:1080 rus.sixty9.ru
nix run .#import-izbirkom
```

Override it without editing: `nix run .#import-izbirkom -- --proxy http://localhost:8080` or `VIBORI_PROXY=http://localhost:8080 nix run .#import-izbirkom`. Priority is `--proxy` → `VIBORI_PROXY` → config. The `start` event reports the proxy host without credentials.

```bash
nix run .#import-izbirkom
nix run .#build-index
```

Start with `nix run .#import-izbirkom -- --dry-run --max-pages 100`. Imports are resumable because downloaded HTML is not requested again. `--only-vrn <identifier>` limits one campaign. The scraper emits JSON Lines events: `start`, `fetch`, `retry`, `progress`, `protocol`, and `complete`; set summary progress frequency with `progress_every_pages`. It does not bypass site protections or treat incomplete pages as results.
