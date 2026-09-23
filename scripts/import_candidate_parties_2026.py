"""Import documented candidate affiliations for 2026 single-member results."""

import hashlib
import html
import json
import os
import re
import time
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from import_izbirkom_api import make_opener

ELECTION_ID = "izbirkom-587813923-p1"
SOURCE_BASE = "https://www.iditena.org/districts"
USER_AGENT = "Mozilla/5.0 (compatible; ViboriCandidateImporter/1.0)"
PARTIES = {
    "\u0415\u0434\u0438\u043d\u0430\u044f \u0420\u043e\u0441\u0441\u0438\u044f": "party-united-russia",
    "\u041a\u041f\u0420\u0424": "party-kprf",
    "\u041b\u0414\u041f\u0420": "party-ldpr",
    "\u0421\u043f\u0440\u0430\u0432\u0435\u0434\u043b\u0438\u0432\u0430\u044f \u0420\u043e\u0441\u0441\u0438\u044f": "party-fair-russia",
    "\u041d\u043e\u0432\u044b\u0435 \u043b\u044e\u0434\u0438": "party-new-people",
    "\u042f\u0431\u043b\u043e\u043a\u043e": "party-yabloko",
    "\u0420\u043e\u0434\u0438\u043d\u0430": "party-rodina",
    "\u041a\u043e\u043c\u043c\u0443\u043d\u0438\u0441\u0442\u044b \u0420\u043e\u0441\u0441\u0438\u0438": "party-communists-russia",
    "\u041f\u0430\u0440\u0442\u0438\u044f \u043f\u0440\u044f\u043c\u043e\u0439 \u0434\u0435\u043c\u043e\u043a\u0440\u0430\u0442\u0438\u0438": "party-direct-democracy",
    "\u041f\u041f\u0414": "party-direct-democracy",
    "\u041f\u0430\u0440\u0442\u0438\u044f \u0420\u043e\u0441\u0442\u0430": "party-growth",
    "\u041f\u0430\u0440\u0442\u0438\u044f \u043f\u0435\u043d\u0441\u0438\u043e\u043d\u0435\u0440\u043e\u0432": "party-pensioners",
    "\u0413\u0440\u0430\u0436\u0434\u0430\u043d\u0441\u043a\u0430\u044f \u043f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u0430": "party-civic-platform",
    "\u0417\u0435\u043b\u0451\u043d\u044b\u0435": "party-greens",
    "\u0417\u0435\u043b\u0435\u043d\u044b\u0435": "party-greens",
    "\u0420\u043e\u0441\u0441\u0438\u0439\u0441\u043a\u0430\u044f \u043f\u0430\u0440\u0442\u0438\u044f \u0441\u0432\u043e\u0431\u043e\u0434\u044b \u0438 \u0441\u043f\u0440\u0430\u0432\u0435\u0434\u043b\u0438\u0432\u043e\u0441\u0442\u0438": "party-rpss",
    "\u0420\u043e\u0441\u0441\u0438\u0439\u0441\u043a\u0438\u0439 \u043e\u0431\u0449\u0435\u043d\u0430\u0440\u043e\u0434\u043d\u044b\u0439 \u0441\u043e\u044e\u0437": "party-ros",
    "\u0417\u0435\u043b\u0451\u043d\u0430\u044f \u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u0430": "party-green-alternative",
}
CARD_PATTERN = re.compile(r'data-pdf-candidate="([^"]+)"')
FIELD_PATTERN = re.compile(
    r'data-pdf-(name|party)="true"[^>]*>(.*?)</(?:span|strong)>', re.DOTALL
)
DISTRICT_PATTERN = re.compile(
    r"\u041e\u043a\u0440\u0443\u0433 \u2116\s*(\d+),\s*(.*?)\s*:\s*\u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442\u044b",
    re.DOTALL | re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)


def normalized(value: str) -> str:
    return re.sub(r"[^\w]", "", value.upper().replace("\u0401", "\u0415"))


def entity_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "entity"
    digest = hashlib.sha1(name.encode()).hexdigest()[:10]
    return f"entity-{slug}-{digest}"


def fetch_district(opener: object, number: int) -> dict[str, object] | None:
    url = f"{SOURCE_BASE}/{number}/"
    for attempt in range(3):
        request = Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
        )
        try:
            with opener.open(request, timeout=30) as response:  # type: ignore[attr-defined]
                page = response.read().decode("utf-8")
            retrieved_at = datetime.now(timezone.utc).isoformat()
            district_match = DISTRICT_PATTERN.search(page)
            title_match = TITLE_PATTERN.search(page)
            if not district_match or not title_match:
                return None
            candidates = []
            for marker in CARD_PATTERN.finditer(page):
                section = page[marker.end() : marker.end() + 1800]
                fields = {
                    key: html.unescape(re.sub(r"<[^>]*>", "", value)).strip()
                    for key, value in FIELD_PATTERN.findall(section)
                }
                if fields.get("name") and fields.get("party"):
                    candidates.append(fields)
            return {
                "number": int(district_match.group(1)),
                "region": html.unescape(district_match.group(2)).strip(),
                "district": html.unescape(
                    re.sub(r"<[^>]*>", "", title_match.group(1))
                ).strip(),
                "source_url": url,
                "retrieved_at": retrieved_at,
                "candidates": candidates,
            }
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
        time.sleep(attempt + 1)
    return None


def collect_results(election_dir: Path) -> dict[str, dict[str, object]]:
    candidates: dict[str, dict[str, object]] = {}
    for folder in ("precincts", "aggregates"):
        for path in (election_dir / folder).glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            unit = record.get("unit") or {}
            district = (
                unit
                if unit.get("kind") == "district"
                else next(
                    (
                        item
                        for item in unit.get("administrative_path") or []
                        if item.get("kind") == "district"
                    ),
                    None,
                )
            )
            if not district:
                continue
            for result in record.get("results") or []:
                entity = result.get("entity") or {}
                if entity.get("type") != "candidate":
                    continue
                current = candidates.setdefault(
                    entity["id"],
                    {
                        "id": entity["id"],
                        "name": entity["name"],
                        "district_name": district["name"],
                    },
                )
                if (
                    current["name"] != entity["name"]
                    or current["district_name"] != district["name"]
                ):
                    raise ValueError(
                        f"Conflicting candidate identity for {entity['id']}"
                    )
    return candidates


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("public/data"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--proxy")
    parser.add_argument("--no-proxy", action="store_true")
    args = parser.parse_args()
    proxy = None if args.no_proxy else args.proxy or os.environ.get("VIBORI_PROXY")
    opener = make_opener(proxy)
    election_dir = args.data / ELECTION_ID
    results = collect_results(election_dir)

    districts: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
        futures = [
            executor.submit(fetch_district, opener, number) for number in range(1, 226)
        ]
        for future in as_completed(futures):
            page = future.result()
            if page:
                district = normalized(str(page["region"]))
                number = str(page["number"])
                districts[f"{district}:{number}"] = page

    page_by_district = list(districts.values())
    party_ids = {normalized(name): identifier for name, identifier in PARTIES.items()}
    assigned = 0
    for candidate in results.values():
        district_name = normalized(str(candidate["district_name"]))
        district_pages = [
            page
            for page in page_by_district
            if normalized(str(page["region"])) in district_name
            and normalized(str(page["district"])) in district_name
        ]
        name = normalized(str(candidate["name"]))
        matches = [
            (page, item)
            for page in district_pages
            for item in page["candidates"]
            if normalized(str(item["name"])) == name
        ]
        parties = {str(item["party"]) for _, item in matches}
        if len(parties) != 1:
            continue
        page = min(matches, key=lambda match: int(match[0]["number"]))[0]
        party_name = parties.pop()
        party = None
        if normalized(party_name) != (
            "\u0421\u0410\u041c\u041e\u0412\u042b\u0414\u0412\u0418\u0416\u0415\u041d\u0418\u0415"
        ):
            party = {
                "id": party_ids.get(normalized(party_name), entity_id(party_name)),
                "name": party_name,
            }
        target = election_dir / "candidates" / f"{candidate['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        profile = {
            "standard": "vibori-candidate/v1",
            "source": {
                "url": page["source_url"],
                "retrieved_at": page["retrieved_at"],
                "publisher": "IditeNa.org",
            },
            "id": candidate["id"],
            "name": candidate["name"],
            "election_id": ELECTION_ID,
            "party": party,
            "district_number": page["number"],
        }
        target.write_text(
            json.dumps(profile, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        assigned += 1
    print(
        f"Imported party affiliations for {assigned} of {len(results)} result candidates"
    )


if __name__ == "__main__":
    main()
