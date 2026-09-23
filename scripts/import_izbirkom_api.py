"""Import every accessible precinct protocol from the izbirkom.ru SPA API."""

import hashlib
import json
import mimetypes
import os
import re
import socket
import time
from argparse import ArgumentParser
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeAlias
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from izbirkom_api import ApiError, IzbirkomApi

JsonObject: TypeAlias = dict[str, Any]
TreeEntry: TypeAlias = tuple[JsonObject, list[JsonObject]]
TreeStackEntry: TypeAlias = tuple[JsonObject, list[JsonObject], str | None]
BatchEntry: TypeAlias = tuple[JsonObject, list[JsonObject], int, Path]
PARTY_LOGOS: list[JsonObject] = []
FALLBACK_PARTY_COLORS = {
    "party-fair-russia": "#d52b1e",
    "party-kprf": "#cc1f2f",
    "party-ldpr": "#1e4b9b",
    "party-new-people": "#6e4bca",
    "party-rodina": "#b21f31",
    "party-united-russia": "#006ab3",
    "party-yabloko": "#3d9c35",
}


def emit(event: str, **data: object) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_opener(proxy: str | None) -> OpenerDirector:
    if not proxy:
        return build_opener(ProxyHandler({}))
    parsed = urlparse(proxy)
    if parsed.scheme in ("socks5", "socks5h"):
        import socks

        socks.setdefaultproxy(
            socks.PROXY_TYPE_SOCKS5,
            parsed.hostname,
            parsed.port or 1080,
            rdns=parsed.scheme == "socks5h",
        )
        socket.socket = socks.socksocket  # type: ignore[misc]
        return build_opener(ProxyHandler({}))
    if parsed.scheme not in ("http", "https"):
        raise SystemExit("Proxy must use http://, https://, socks5://, or socks5h://")
    return build_opener(ProxyHandler({"http": proxy, "https": proxy}))


@lru_cache(maxsize=8192)
def entity_id(name: str) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (ascii_slug or "entity") + "-" + hashlib.sha1(name.encode()).hexdigest()[:10]


def party_id(name: str) -> str:
    normalized = name.upper().replace("Ё", "Е")
    for party in PARTY_LOGOS:
        if any(
            str(pattern).replace("Ё", "Е") in normalized
            for pattern in party["patterns"]
        ):
            return str(party["id"])
    return entity_id(name)


def mediawiki_logo(
    opener: OpenerDirector, title: str, user_agent: str
) -> tuple[bytes, str, str]:
    def open_request(request: Request) -> Any:
        for attempt in range(5):
            try:
                return opener.open(request, timeout=45)
            except HTTPError as error:
                if error.code != 429 or attempt == 4:
                    raise
                time.sleep(int(error.headers.get("Retry-After", "5")))
        raise RuntimeError("MediaWiki request exhausted retries")

    query = urlencode(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "format": "json",
            "origin": "*",
        }
    )
    api_url = f"https://ru.wikipedia.org/w/api.php?{query}"
    request = Request(
        api_url, headers={"Accept": "application/json", "User-Agent": user_agent}
    )
    with open_request(request) as response:
        payload = json.load(response)
    page = next(iter(payload["query"]["pages"].values()))
    image = page["imageinfo"][0]
    image_url = image["url"]
    request = Request(image_url, headers={"User-Agent": user_agent})
    time.sleep(1)
    with open_request(request) as response:
        return (
            response.read(),
            image.get("mime") or response.headers.get_content_type(),
            image.get("descriptionurl") or api_url,
        )


def normalize_logo(content: bytes, mime_type: str) -> bytes:
    if mime_type != "image/svg+xml":
        return content
    return b"\n".join(line.rstrip(b" \t\r") for line in content.splitlines()) + b"\n"


def logo_color(content: bytes, mime_type: str, fallback: str) -> str:
    """Choose the most frequent saturated SVG color that remains visible on white."""
    if mime_type != "image/svg+xml":
        return fallback
    counts: dict[str, int] = {}
    for match in re.finditer(rb"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", content):
        raw = match.group().decode().lower()
        color = (
            "#" + "".join(channel * 2 for channel in raw[1:]) if len(raw) == 4 else raw
        )
        red, green, blue = (int(color[offset : offset + 2], 16) for offset in (1, 3, 5))
        brightest, darkest = max(red, green, blue), min(red, green, blue)
        if (
            brightest - darkest < 36
            or (red * 299 + green * 587 + blue * 114) / 1000 > 205
        ):
            continue
        counts[color] = counts.get(color, 0) + 1
    return max(counts, key=lambda color: counts[color]) if counts else fallback


def import_party_logos(
    opener: OpenerDirector,
    output: Path,
    user_agent: str,
    dry_run: bool,
) -> None:
    party_file = output / "parties.json"
    existing = (
        json.loads(party_file.read_text(encoding="utf-8"))
        if party_file.exists()
        else []
    )
    records = {item["id"]: item for item in existing}
    for party in PARTY_LOGOS:
        current = records.get(party["id"])
        if current and (output / current["logo"]).exists():
            logo_path = output / current["logo"]
            current["color"] = logo_color(
                logo_path.read_bytes(),
                mimetypes.guess_type(logo_path.name)[0] or "",
                FALLBACK_PARTY_COLORS.get(str(party["id"]), "#356ae6"),
            )
            continue
        content, mime_type, source_url = mediawiki_logo(
            opener, party["mediawiki_file"], user_agent
        )
        content = normalize_logo(content, mime_type)
        digest = hashlib.sha256(content).hexdigest()
        extension = (
            mimetypes.guess_extension(mime_type)
            or Path(urlparse(source_url).path).suffix
            or ".img"
        )
        relative = f"party-logos/{digest}{extension}"
        records[party["id"]] = {
            "id": party["id"],
            "name": party["name"],
            "aliases": party["patterns"],
            "color": logo_color(
                content,
                mime_type,
                FALLBACK_PARTY_COLORS.get(str(party["id"]), "#356ae6"),
            ),
            "logo": relative,
            "source": {
                "url": source_url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "publisher": "Wikimedia Commons",
            },
        }
        if not dry_run:
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(content)
    if not dry_run:
        party_file.parent.mkdir(parents=True, exist_ok=True)
        party_file.write_text(
            json.dumps(
                sorted(records.values(), key=lambda item: item["id"]),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )


def election_pages(
    api: IzbirkomApi,
    date_from: str,
    date_to: str,
    page_size: int,
    only_id: int | None,
    max_elections: int | None,
) -> Iterator[JsonObject]:
    if only_id:
        yield api.get(f"/elections/{only_id}")
        return
    page = 1
    yielded = 0
    while True:
        response = api.elections(date_from, date_to, page, page_size)
        content = response.get("content") or []
        emit(
            "election_page",
            page=page,
            pages=response.get("totalPages"),
            elections=response.get("totalSize"),
            received=len(content),
        )
        for election in content:
            yield election
            yielded += 1
            if max_elections and yielded >= max_elections:
                return
        if page >= response.get("totalPages", page) or not content:
            return
        page += 1


def children(
    api: IzbirkomApi,
    election_id: int,
    node: JsonObject | None,
    subject_code: str | None,
) -> JsonObject:
    params: JsonObject = {"electionsId": election_id}
    if subject_code and subject_code != "00":
        params["subjectRf"] = subject_code
    if node:
        params["classifierId"] = node["externalId"]
    return api.get("/commissionClassifiers", params)


def walk_precincts(
    api: IzbirkomApi,
    election: JsonObject,
) -> Iterator[TreeEntry]:
    subject = str((election.get("subjectRf") or {}).get("externalId") or "") or None
    root = children(api, election["id"], None, subject)
    stack: list[TreeStackEntry] = [(root, [], None)]
    while stack:
        node, path, subject_code = stack.pop()
        node_type = int(node.get("type", -1))
        next_subject = subject_code
        if node_type == 2:
            next_subject = str(node.get("number", "")).zfill(2)
        current_path = path + [node]
        if node_type == 5 or not node.get("hasChildren"):
            if node_type == 5:
                yield node, current_path
            continue
        expanded = (
            node
            if node.get("children")
            else children(api, election["id"], node, next_subject)
        )
        for child in reversed(expanded.get("children") or []):
            stack.append((child, current_path, next_subject))


def unit_kind(node: JsonObject) -> str:
    return {
        0: "national",
        2: "region",
        3: "district",
        4: "territorial_commission",
        5: "precinct",
    }.get(int(node.get("type", -1)), "other")


def is_party_protocol(election: JsonObject, protocol_num: int) -> bool:
    system = str((election.get("systemType") or {}).get("externalId", ""))
    return system == "2" or (system == "3" and protocol_num == 2)


def vote_count(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing or invalid vote count")
    text = str(value).strip()
    if not text.isdecimal():
        raise ValueError("Vote count must be a non-negative integer")
    return int(text)


def candidate_record(
    api_base: str,
    election: JsonObject,
    summary: JsonObject,
    detail: JsonObject,
    protocol_num: int,
) -> JsonObject:
    party_name = summary.get("electionAssociation") or None
    candidate_id = summary["id"]
    profile = detail.get("body") or {}
    return {
        "standard": "vibori-candidate/v1",
        "source": {
            "url": f"{api_base.rstrip('/')}/reports/341?candidateId={candidate_id}",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publisher": "Central Election Commission of Russia",
        },
        "id": candidate_id,
        "name": summary["fullName"],
        "election_id": f"izbirkom-{election['id']}-p{protocol_num}",
        "party": (
            {"id": party_id(party_name), "name": party_name}
            if party_name and party_name != "Самовыдвижение"
            else None
        ),
        "birth_date": profile.get("birthDate") or summary.get("birthDate"),
        "birth_place": profile.get("birthPlace"),
        "address": profile.get("regAddressPublic"),
        "education": profile.get("education"),
        "work": profile.get("work"),
        "position": profile.get("position"),
        "status": profile.get("status") or summary.get("enrollment"),
        "convictions": profile.get("convictions"),
        "foreign_agent": profile.get("foreignAgent"),
        "candidate_vrn": profile.get("candidateVrn"),
        "district_number": summary.get("districtNum") or None,
        "regional_group": summary.get("regionalGroup"),
        "number_in_list": summary.get("numberInList"),
        "nomination": summary.get("nomination"),
        "registration": summary.get("enrollment"),
        "registration_date": summary.get("regDate"),
    }


def candidate_pages(api: IzbirkomApi, election: JsonObject) -> list[JsonObject]:
    candidates: list[JsonObject] = []
    page = 1
    while True:
        response = api.post(
            "/candidate/paging",
            {
                "electionsId": election["externalId"],
                "showSelfNominated": True,
                "page": page,
                "perPage": 500,
            },
        )
        candidates.extend(response.get("content") or [])
        if page >= response.get("totalPages", page):
            return candidates
        page += 1


def import_candidates(
    api: IzbirkomApi,
    api_base: str,
    election: JsonObject,
    output: Path,
    executor: ThreadPoolExecutor,
    dry_run: bool,
    totals: dict[str, int],
) -> dict[int, dict[str, list[JsonObject]]]:
    summaries = candidate_pages(api, election)
    by_protocol: dict[int, dict[str, list[JsonObject]]] = {
        protocol_num: {} for protocol_num in protocol_numbers(election)
    }
    pending = {
        executor.submit(api.get, "/reports/341", {"candidateId": item["id"]}): item
        for item in summaries
        if not (
            output
            / f"izbirkom-{election['id']}-p{1 if item.get('districtNum') else (2 if 2 in by_protocol else 1)}"
            / "candidates"
            / f"{item['id']}.json"
        ).exists()
    }
    for summary in summaries:
        protocol_num = (
            1 if summary.get("districtNum") else (2 if 2 in by_protocol else 1)
        )
        target = (
            output
            / f"izbirkom-{election['id']}-p{protocol_num}"
            / "candidates"
            / f"{summary['id']}.json"
        )
        if target.exists():
            record = json.loads(target.read_text(encoding="utf-8"))
            by_protocol[protocol_num].setdefault(summary["fullName"], []).append(record)
    for future in as_completed(pending):
        summary = pending[future]
        try:
            detail = future.result()
            protocol_num = (
                1 if summary.get("districtNum") else (2 if 2 in by_protocol else 1)
            )
            record = candidate_record(api_base, election, summary, detail, protocol_num)
            by_protocol[protocol_num].setdefault(summary["fullName"], []).append(record)
            if not dry_run:
                target = (
                    output
                    / record["election_id"]
                    / "candidates"
                    / f"{record['id']}.json"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
            totals["candidates"] += 1
        except (
            ApiError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            totals["errors"] += 1
            emit(
                "candidate_error",
                election=election["id"],
                candidate=summary.get("id"),
                error=str(error),
            )
    emit("candidates", election=election["id"], imported=len(summaries))
    return by_protocol


def enrich_existing_protocol(
    target: Path, candidates: dict[str, list[JsonObject]]
) -> bool:
    record: JsonObject = json.loads(target.read_text(encoding="utf-8"))
    path: list[JsonObject] = (record.get("unit") or {}).get("administrative_path") or []
    district: JsonObject = next(
        (item for item in reversed(path) if item.get("kind") == "district"), {}
    )
    district_number = str(district.get("number") or "").lstrip("0")
    changed = False
    for result in record.get("results") or []:
        entity = result.get("entity") or {}
        if entity.get("type") == "party" and isinstance(entity.get("name"), str):
            replacement = {
                "id": party_id(entity["name"]),
                "name": entity["name"],
                "type": "party",
            }
            if replacement != entity:
                result["entity"] = replacement
                changed = True
            continue
        if entity.get("type") != "candidate":
            continue
        name = entity.get("name")
        if not isinstance(name, str):
            continue
        matches = candidates.get(name, [])
        match = next(
            (
                item
                for item in matches
                if str(item.get("district_number") or "").lstrip("0") == district_number
            ),
            matches[0] if len(matches) == 1 else None,
        )
        if not match:
            continue
        replacement = {"id": match["id"], "name": entity["name"], "type": "candidate"}
        if match.get("party"):
            replacement["party_id"] = match["party"]["id"]
            replacement["party_name"] = match["party"]["name"]
        if replacement != entity:
            result["entity"] = replacement
            changed = True
    if changed:
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    return changed


def report_to_record(
    api_base: str,
    election: JsonObject,
    unit: JsonObject,
    path: list[JsonObject],
    protocol_num: int,
    report: JsonObject,
    candidates: dict[str, list[JsonObject]] | None = None,
) -> JsonObject | None:
    body = report.get("body") or {}
    records = body.get("records") or []
    counters = {
        str(row.get("infoNum") or row.get("infoPrintNum")): vote_count(row.get("value"))
        for row in records
        if row.get("category") == "records"
    }
    choices = [row for row in records if row.get("category") != "records"]
    if not choices:
        return None
    if not {"1", "3", "4", "5", "9", "10"}.issubset(counters):
        raise ValueError("Protocol is missing required turnout counters")
    election_id = f"izbirkom-{election['id']}-p{protocol_num}"
    hierarchy = []
    for item in path[:-1]:
        hierarchy.append(
            {"id": item["externalId"], "name": item["name"], "kind": unit_kind(item)}
        )
    party_protocol = is_party_protocol(election, protocol_num)
    entity_type = "party" if party_protocol else "candidate"
    report_url = (
        api_base.rstrip("/")
        + "/reports/242?"
        + urlencode(
            {"commissionClassifierId": unit["externalId"], "protocolNum": protocol_num}
        )
    )
    scope = {"1": "national", "2": "regional", "3": "municipal"}.get(
        str((election.get("electionLevel") or {}).get("externalId", "")), "other"
    )

    def result_entity(row: JsonObject) -> JsonObject:
        name = row["infoText"]
        if entity_type == "party":
            return {"id": party_id(name), "name": name, "type": entity_type}
        matches = (candidates or {}).get(name, [])
        district = next(
            (item for item in reversed(path) if unit_kind(item) == "district"), {}
        )
        district_number = str(district.get("number") or "").lstrip("0")
        match = next(
            (
                item
                for item in matches
                if str(item.get("district_number") or "").lstrip("0") == district_number
            ),
            matches[0] if len(matches) == 1 else None,
        )
        if not match:
            return {"id": entity_id(name), "name": name, "type": entity_type}
        entity = {"id": match["id"], "name": name, "type": entity_type}
        if match.get("party"):
            entity["party_id"] = match["party"]["id"]
            entity["party_name"] = match["party"]["name"]
        return entity

    return {
        "standard": "vibori-election-result/v1",
        "source": {
            "url": report_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publisher": "Central Election Commission of Russia",
        },
        "election": {
            "id": election_id,
            "name": election["name"],
            "country": "RU",
            "date": election["votingDate"],
            "scope": scope,
        },
        "unit": {
            "id": unit["externalId"],
            "name": unit["name"],
            "number": str(unit.get("number", "")),
            "kind": unit_kind(unit),
            "administrative_path": hierarchy,
        },
        "ballot": {
            "id": f"protocol-{protocol_num}",
            "title": election["name"],
            "kind": "party_list" if party_protocol else "single_member",
        },
        "turnout": {
            "registered": counters.get("1", 0),
            "issued": counters.get("3", 0)
            + counters.get("4", 0)
            + counters.get("5", 0),
            "valid": counters.get("10", 0),
            "invalid": counters.get("9", 0),
        },
        "results": [
            {
                "entity": {
                    **result_entity(row),
                },
                "votes": vote_count(row.get("value")),
            }
            for row in choices
        ],
    }


def protocol_numbers(election: JsonObject) -> tuple[int, ...]:
    kind = str((election.get("kind") or {}).get("externalId", ""))
    system = str((election.get("systemType") or {}).get("externalId", ""))
    if kind == "2" and system == "3":
        return (1, 2)
    if kind == "2" and system == "2":
        return (1,)
    return (1,)


def import_batch(
    api: IzbirkomApi,
    api_base: str,
    election: JsonObject,
    batch: list[BatchEntry],
    executor: ThreadPoolExecutor,
    dry_run: bool,
    totals: dict[str, int],
    candidates: dict[int, dict[str, list[JsonObject]]],
) -> None:
    pending = {
        executor.submit(
            api.get,
            "/reports/242",
            {
                "commissionClassifierId": unit["externalId"],
                "protocolNum": protocol_num,
            },
        ): (unit, path, protocol_num, target)
        for unit, path, protocol_num, target in batch
    }
    for future in as_completed(pending):
        unit, path, protocol_num, target = pending[future]
        try:
            report = future.result()
            record = report_to_record(
                api_base,
                election,
                unit,
                path,
                protocol_num,
                report,
                candidates.get(protocol_num),
            )
            if not record:
                totals["skipped"] += 1
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    + "\n",
                    encoding="utf-8",
                )
                temporary.replace(target)
            totals["protocols"] += 1
            if unit_kind(unit) != "precinct":
                totals["official_aggregates"] += 1
            emit(
                "protocol",
                election=election["id"],
                unit=unit.get("name"),
                unit_kind=unit_kind(unit),
                protocol=protocol_num,
                imported=totals["protocols"],
            )
        except ApiError as error:
            if error.status == 404:
                totals["unavailable"] += 1
                emit(
                    "protocol_unavailable",
                    election=election["id"],
                    unit=unit.get("name"),
                    unit_kind=unit_kind(unit),
                    protocol=protocol_num,
                )
                continue
            totals["errors"] += 1
            emit(
                "protocol_error",
                election=election["id"],
                unit=unit.get("name"),
                unit_kind=unit_kind(unit),
                protocol=protocol_num,
                error=str(error),
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            totals["errors"] += 1
            emit(
                "protocol_error",
                election=election["id"],
                unit=unit.get("name"),
                unit_kind=unit_kind(unit),
                protocol=protocol_num,
                error=str(error),
            )


def main() -> None:
    load_dotenv()
    parser = ArgumentParser()
    parser.add_argument("--config", default="config/izbirkom.json")
    parser.add_argument("--out", default="public/data")
    parser.add_argument("--date-from", default="2000-01-01")
    parser.add_argument("--date-to", default="2035-12-31")
    parser.add_argument("--election-id", type=int)
    parser.add_argument("--max-elections", type=int)
    parser.add_argument("--max-precincts", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--proxy")
    parser.add_argument("--no-proxy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    PARTY_LOGOS.extend(config.get("party_logos") or [])
    proxy = (
        None
        if args.no_proxy
        else args.proxy
        or os.environ.get("VIBORI_PROXY")
        or config["request"].get("proxy")
    )
    api_base = config["api"]["base_url"]
    user_agent = config["request"]["user_agent"]
    api = IzbirkomApi(
        make_opener(proxy),
        api_base,
        user_agent,
        config["request"]["timeout_seconds"],
        config["request"]["retries"],
        config["request"].get("delay_seconds", 0),
    )
    output = Path(args.out)
    import_party_logos(api.opener, output, user_agent, args.dry_run)
    totals = {
        "elections": 0,
        "precincts": 0,
        "protocols": 0,
        "candidates": 0,
        "official_aggregates": 0,
        "unavailable": 0,
        "skipped": 0,
        "errors": 0,
    }
    emit(
        "start",
        date_from=args.date_from,
        date_to=args.date_to,
        proxy=urlparse(proxy).hostname if proxy else None,
    )
    for election in election_pages(
        api, args.date_from, args.date_to, 100, args.election_id, args.max_elections
    ):
        totals["elections"] += 1
        emit(
            "election",
            id=election["id"],
            name=election["name"],
            index=totals["elections"],
        )
        try:
            units: dict[str, TreeEntry] = {}
            precinct_count = 0
            for precinct in walk_precincts(api, election):
                precinct_count += 1
                for index, unit in enumerate(precinct[1]):
                    units.setdefault(
                        unit["externalId"], (unit, precinct[1][: index + 1])
                    )
                if args.progress_every and precinct_count % args.progress_every == 0:
                    emit(
                        "tree_progress",
                        election=election["id"],
                        precincts=precinct_count,
                    )
                if args.max_precincts and precinct_count >= args.max_precincts:
                    break
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            totals["errors"] += 1
            emit("election_error", id=election["id"], error=str(error))
            continue
        totals["precincts"] += precinct_count
        with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
            try:
                candidates = import_candidates(
                    api, api_base, election, output, executor, args.dry_run, totals
                )
            except (
                ApiError,
                KeyError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                totals["errors"] += 1
                candidates = {number: {} for number in protocol_numbers(election)}
                emit(
                    "candidate_import_error", election=election["id"], error=str(error)
                )
            batch: list[BatchEntry] = []
            batch_size = max(args.workers, 1) * 4
            for unit, path in units.values():
                for protocol_num in protocol_numbers(election):
                    folder = (
                        "precincts" if unit_kind(unit) == "precinct" else "aggregates"
                    )
                    target = (
                        output
                        / f"izbirkom-{election['id']}-p{protocol_num}"
                        / folder
                        / f"{unit['externalId']}.json"
                    )
                    if target.exists():
                        if not args.dry_run and protocol_num in candidates:
                            enrich_existing_protocol(target, candidates[protocol_num])
                        totals["skipped"] += 1
                        continue
                    batch.append((unit, path, protocol_num, target))
                    if len(batch) >= batch_size:
                        import_batch(
                            api,
                            api_base,
                            election,
                            batch,
                            executor,
                            args.dry_run,
                            totals,
                            candidates,
                        )
                        batch = []
            if batch:
                import_batch(
                    api,
                    api_base,
                    election,
                    batch,
                    executor,
                    args.dry_run,
                    totals,
                    candidates,
                )
    emit("complete", **totals, next="nix run .#build-index")


if __name__ == "__main__":
    main()
