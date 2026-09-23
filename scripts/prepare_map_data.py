"""Normalize and simplify the external federal-subject GeoJSON for the UI."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def perpendicular_distance(
    point: list[float], start: list[float], end: list[float]
) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    if dx == 0 and dy == 0:
        return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** 0.5
    return (
        abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0])
        / (dx * dx + dy * dy) ** 0.5
    )


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 4:
        return points
    open_points = points[:-1] if points[0] == points[-1] else points
    first, last = open_points[0], open_points[-1]
    distance, split = max(
        (perpendicular_distance(point, first, last), index)
        for index, point in enumerate(open_points[1:-1], 1)
    )
    if distance <= tolerance:
        result = [first, last]
    else:
        result = simplify(open_points[: split + 1], tolerance)[:-1] + simplify(
            open_points[split:], tolerance
        )
    return result + [result[0]]


def normalize_geometry(geometry: dict[str, Any], tolerance: float) -> dict[str, Any]:
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    normalized = []
    for polygon in polygons:
        rings = [
            simplify(
                [[round(value, 4) for value in point[:2]] for point in ring], tolerance
            )
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
    parser.add_argument("--tolerance", type=float, default=0.08)
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
                "geometry": normalize_geometry(feature["geometry"], args.tolerance),
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
