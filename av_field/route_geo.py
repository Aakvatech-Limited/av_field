"""Pure GeoJSON point selection and Geoapify response validation."""
import json
import math


class RoutingError(ValueError):
    pass


def point_from_geojson(value):
    """Return [longitude, latitude] for exactly one unambiguous Point feature.

    GeoJSON uses lon/lat, unlike Leaflet's LatLng UI array. We deliberately
    reject ambiguous multi-point geometries rather than route to the wrong site.
    """
    try:
        data = json.loads(value) if isinstance(value, str) else value
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise RoutingError("Geolocation must contain a GeoJSON FeatureCollection")
        features = data.get("features")
        if not isinstance(features, list):
            raise RoutingError("Geolocation features are invalid")
        points = [f["geometry"]["coordinates"] for f in features
                  if isinstance(f, dict) and isinstance(f.get("geometry"), dict)
                  and f["geometry"].get("type") == "Point"]
        if len(points) != 1 or len(features) != 1:
            raise RoutingError("Select exactly one point marker on the Address")
        coords = points[0]
        if not isinstance(coords, list) or len(coords) < 2:
            raise RoutingError("Point coordinates are invalid")
        lon, lat = coords[:2]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in (lon, lat)):
            raise RoutingError("Point coordinates must be finite numbers")
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise RoutingError("Point coordinates are outside valid ranges")
        return [float(lon), float(lat)]
    except (TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RoutingError("Address Geolocation contains invalid GeoJSON") from exc


def optimized_jobs(result, expected_ids):
    """Extract job sequence and estimated arrival seconds; refuse partial answers."""
    if not isinstance(result, dict) or result.get("type") != "FeatureCollection":
        raise RoutingError("Invalid Geoapify route response")
    if result.get("properties", {}).get("issues"):
        issues = result["properties"]["issues"]
        if any(v for k, v in issues.items() if "unassigned" in k.lower()):
            raise RoutingError("Geoapify could not schedule all requested visits")
    features = result.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise RoutingError("Expected one Geoapify agent route")
    props = features[0].get("properties") or {}
    actions = props.get("actions") or []
    seen = []
    for action in actions:
        if action.get("type") != "job":
            continue
        job_id = action.get("job_id")
        if job_id is None and isinstance(action.get("job_index"), int):
            idx = action["job_index"]
            if 0 <= idx < len(expected_ids):
                job_id = expected_ids[idx]
        if job_id not in expected_ids or job_id in [x["id"] for x in seen]:
            raise RoutingError("Geoapify returned an unexpected or duplicate job")
        seen.append({"id": job_id, "arrival_seconds": action.get("start_time")})
    if {entry["id"] for entry in seen} != set(expected_ids):
        raise RoutingError("Geoapify returned a partial route")
    distance = props.get("distance")
    travel_time = props.get("time")
    if not isinstance(distance, (int, float)) or not isinstance(travel_time, (int, float)):
        raise RoutingError("Geoapify did not provide route totals")
    return seen, float(distance), float(travel_time)
