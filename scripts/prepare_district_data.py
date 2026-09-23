"""Extract the published 2026 district number/name lookup from a saved HTML page."""

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


class DistrictParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_region_heading = False
        self.region = ""
        self.districts: list[dict[str, str | int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h3":
            self.in_region_heading = True
        label = attributes.get("aria-label") or ""
        match = re.match(r"Округ № (\d+), ([^.]+)", label)
        if tag == "a" and match:
            self.districts.append(
                {
                    "region": self.region,
                    "number": int(match.group(1)),
                    "name": match.group(2),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self.in_region_heading = False

    def handle_data(self, data: str) -> None:
        if self.in_region_heading and data.strip():
            self.region = data.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    district_parser = DistrictParser()
    district_parser.feed(args.source.read_text())
    output = {
        "source": {
            "url": "https://iditena.org/",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publisher": "Idite na",
        },
        "districts": district_parser.districts,
    }
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n"
    )


if __name__ == "__main__":
    main()
