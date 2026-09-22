"""Import every accessible precinct protocol from the izbirkom.ru SPA API."""

import hashlib
import json
import os
import re
import socket
from argparse import ArgumentParser
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urlencode, urlparse
from urllib.request import OpenerDirector, ProxyHandler, build_opener

from izbirkom_api import ApiError, IzbirkomApi

JsonObject: TypeAlias = dict[str, Any]
TreeEntry: TypeAlias = tuple[JsonObject, list[JsonObject]]
TreeStackEntry: TypeAlias = tuple[JsonObject, list[JsonObject], str | None]
BatchEntry: TypeAlias = tuple[JsonObject, list[JsonObject], int, Path]


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


def entity_id(name: str) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (ascii_slug or "entity") + "-" + hashlib.sha1(name.encode()).hexdigest()[:10]


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


def report_to_record(
    api_base: str,
    election: JsonObject,
    unit: JsonObject,
    path: list[JsonObject],
    protocol_num: int,
    report: JsonObject,
) -> JsonObject | None:
    body = report.get("body") or {}
    records = body.get("records") or []
    counters = {
        str(row.get("infoPrintNum")): int(row.get("value") or 0)
        for row in records
        if row.get("category") == "records"
    }
    choices = [row for row in records if row.get("category") != "records"]
    if not choices:
        return None
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
                    "id": entity_id(row["infoText"]),
                    "name": row["infoText"],
                    "type": entity_type,
                },
                "votes": int(row.get("value") or 0),
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
    workers: int,
    dry_run: bool,
    totals: dict[str, int],
) -> None:
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
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
                    api_base, election, unit, path, protocol_num, report
                )
                if not record:
                    totals["skipped"] += 1
                    continue
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8",
                    )
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
    )
    output = Path(args.out)
    totals = {
        "elections": 0,
        "precincts": 0,
        "protocols": 0,
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
            precincts = []
            for precinct in walk_precincts(api, election):
                precincts.append(precinct)
                if args.progress_every and len(precincts) % args.progress_every == 0:
                    emit(
                        "tree_progress",
                        election=election["id"],
                        precincts=len(precincts),
                    )
                if args.max_precincts and len(precincts) >= args.max_precincts:
                    break
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            totals["errors"] += 1
            emit("election_error", id=election["id"], error=str(error))
            continue
        totals["precincts"] += len(precincts)
        units: dict[str, TreeEntry] = {}
        for _precinct, path in precincts:
            for index, unit in enumerate(path):
                units[unit["externalId"]] = (unit, path[: index + 1])
        batch: list[BatchEntry] = []
        batch_size = max(args.workers, 1) * 4
        for unit, path in units.values():
            for protocol_num in protocol_numbers(election):
                folder = "precincts" if unit_kind(unit) == "precinct" else "aggregates"
                target = (
                    output
                    / f"izbirkom-{election['id']}-p{protocol_num}"
                    / folder
                    / f"{unit['externalId']}.json"
                )
                if target.exists():
                    totals["skipped"] += 1
                    continue
                batch.append((unit, path, protocol_num, target))
                if len(batch) >= batch_size:
                    import_batch(
                        api,
                        api_base,
                        election,
                        batch,
                        args.workers,
                        args.dry_run,
                        totals,
                    )
                    batch = []
        if batch:
            import_batch(
                api, api_base, election, batch, args.workers, args.dry_run, totals
            )
    emit("complete", **totals, next="nix run .#build-index")


if __name__ == "__main__":
    main()
