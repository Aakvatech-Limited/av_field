"""Provider-independent contract tests: no Frappe/site/API key required."""
import json
import unittest

from av_field.route_geo import RoutingError, optimized_jobs, point_from_geojson


def geo(lon=39.28, lat=-6.82):
    return json.dumps({"type":"FeatureCollection","features":[{
        "type":"Feature","properties":{},"geometry":{
            "type":"Point","coordinates":[lon,lat]}}]})


class TestAddressGeojson(unittest.TestCase):
    def test_tanzania_coordinate_order(self):
        self.assertEqual(point_from_geojson(geo()), [39.28, -6.82])

    def test_reject_multiple_markers(self):
        payload = json.loads(geo())
        payload["features"].append(payload["features"][0])
        with self.assertRaises(RoutingError):
            point_from_geojson(payload)

    def test_reject_invalid_point(self):
        with self.assertRaises(RoutingError):
            point_from_geojson(geo(300, -6.82))

    def test_reject_lines(self):
        with self.assertRaises(RoutingError):
            point_from_geojson({"type":"FeatureCollection", "features":[{
                "type":"Feature","geometry":{"type":"LineString","coordinates":[[39,-6],[40,-7]]}}]})


class TestRoutePlanResponse(unittest.TestCase):
    def response(self, actions):
        return {"type":"FeatureCollection","properties":{"issues":{}},
                "features":[{"properties":{"actions":actions,"distance":10000,"time":1200}}]}

    def test_order_and_eta(self):
        result = self.response([
            {"type":"start"}, {"type":"job","job_id":"job-1","start_time":300},
            {"type":"job","job_id":"job-0","start_time":900},
            {"type":"end"},
        ])
        sequence, distance, seconds = optimized_jobs(result, ["job-0","job-1"])
        self.assertEqual([j["id"] for j in sequence], ["job-1","job-0"])
        self.assertEqual(sequence[0]["arrival_seconds"], 300)
        self.assertEqual((distance,seconds), (10000.0,1200.0))

    def test_missing_visit_must_fail(self):
        with self.assertRaises(RoutingError):
            optimized_jobs(self.response([{"type":"job","job_id":"job-0"}]),
                           ["job-0","job-1"])

    def test_unassigned_jobs_must_fail(self):
        data = self.response([{"type":"job","job_id":"job-0"}])
        data["properties"]["issues"] = {"unassignedJobs":[1]}
        with self.assertRaises(RoutingError):
            optimized_jobs(data, ["job-0"])

    def test_duplicate_visit_must_fail(self):
        with self.assertRaises(RoutingError):
            optimized_jobs(self.response([{"type":"job","job_id":"job-0"},
                                           {"type":"job","job_id":"job-0"}]), ["job-0"])


if __name__ == "__main__":
    unittest.main()
