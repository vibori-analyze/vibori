"""Normalize and simplify the external federal-subject GeoJSON for the UI."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    normalized = []
    for polygon in polygons:
        rings = [
            [[round(value, 4) for value in point[:2]] for point in ring]
            for ring in polygon
        ]
        normalized.append([ring for ring in rings if len(ring) >= 4])
    return (
        {"type": "Polygon", "coordinates": normalized[0]}
        if geometry["type"] == "Polygon"
        else {"type": "MultiPolygon", "coordinates": normalized}
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    features = []
    for feature in source["features"]:
        name = feature["properties"].get("NL_NAME_1") or feature["properties"].get(
            "name"
        )
        if not name or feature["geometry"]["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"name": name},
                "geometry": normalize_geometry(feature["geometry"]),
            }
        )
    output = {
        "type": "FeatureCollection",
        "source": {
            "url": "https://github.com/rnekrasov-msk/geojson/blob/master/russia_subjects_github.json",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publisher": "GADM via rnekrasov-msk/geojson",
        },
        "features": features,
    }
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n"
    )


if __name__ == "__main__":
    main()
