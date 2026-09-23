"""Apply configured stable party identifiers to existing canonical data files."""

import hashlib
import json
import mimetypes
from argparse import ArgumentParser
from pathlib import Path

from import_izbirkom_api import PARTY_LOGOS, entity_id, normalize_logo, party_id


def normalize_logos(data_root: Path) -> int:
    party_file = data_root / "parties.json"
    records = json.loads(party_file.read_text(encoding="utf-8"))
    changed = 0
    for record in records:
        current = data_root / record["logo"]
        mime_type = mimetypes.guess_type(current.name)[0] or ""
        content = normalize_logo(current.read_bytes(), mime_type)
        digest = hashlib.sha256(content).hexdigest()
        target = current.with_name(f"{digest}{current.suffix}")
        if target != current:
            target.write_bytes(content)
            current.unlink()
            record["logo"] = str(target.relative_to(data_root))
            changed += 1
    party_file.write_text(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return changed


def enrich_file(path: Path, legacy: bool = False) -> bool:
    record = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for result in record.get("results") or []:
        entity = result.get("entity") or {}
        if entity.get("type") == "party" and isinstance(entity.get("name"), str):
            stable_id = (
                entity_id(entity["name"]) if legacy else party_id(entity["name"])
            )
            if entity.get("id") != stable_id:
                entity["id"] = stable_id
                changed = True
        party_name = entity.get("party_name")
        if isinstance(party_name, str):
            stable_id = entity_id(party_name) if legacy else party_id(party_name)
            if entity.get("party_id") != stable_id:
                entity["party_id"] = stable_id
                changed = True
    if changed:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    return changed


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--config", default="config/izbirkom.json")
    parser.add_argument("--data", default="public/data")
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--normalize-logos", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    PARTY_LOGOS.extend(config.get("party_logos") or [])
    data_root = Path(args.data)
    party_file = data_root / "parties.json"
    if party_file.exists():
        records = {
            item["id"]: item
            for item in json.loads(party_file.read_text(encoding="utf-8"))
        }
        for party in PARTY_LOGOS:
            if party["id"] in records:
                records[party["id"]]["aliases"] = party["patterns"]
        party_file.write_text(
            json.dumps(
                sorted(records.values(), key=lambda item: item["id"]),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
    logo_count = normalize_logos(data_root) if args.normalize_logos else 0
    changed = (
        0
        if args.catalog_only
        else sum(
            enrich_file(path, args.legacy)
            for folder in ("precincts", "aggregates")
            for path in Path(args.data).glob(f"*/{folder}/*.json")
        )
    )
    print(
        f"Updated party identifiers in {changed} files and normalized {logo_count} logos"
    )


if __name__ == "__main__":
    main()
