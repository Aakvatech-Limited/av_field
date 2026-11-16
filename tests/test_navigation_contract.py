"""Static navigation/analytics integrity tests for AV Field v16 exports.

The tests validate shipped standard source files. Installed record and rendered
permission checks must still run on a Frappe v16.50+ development site.
"""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "av_field"
MODULE = ROOT / "av_field"
WORKSPACE = MODULE / "workspace" / "av_field" / "av_field.json"
SIDEBAR = MODULE / "sidebar" / "av_field" / "av_field.json"
DOCK = ROOT / "dock" / "av_field" / "av_field.json"
DASHBOARD = MODULE / "av_field_dashboard" / "av_field_operations" / "av_field_operations.json"

ROUTE_DOCTYPES = {
    "Field Route Plan": "field_route_plan",
    "Field Call Cycle": "field_call_cycle",
    "Field Route Visit Log": "field_route_visit_log",
    "Field Route Zone": "field_route_zone",
    "Field Route Optimization Settings": "field_route_optimization_settings",
}
CARDS = {
    "Field Routes Total": ("Field Route Plan", []),
    "Field Published Routes": ("Field Route Plan", [["Field Route Plan", "status", "=", "Published"]]),
    "Field Route Outcomes Total": ("Field Route Visit Log", []),
    "Field Postponed Visits": (
        "Field Route Visit Log", [["Field Route Visit Log", "outcome", "=", "Postponed"]]
    ),
}
CHARTS = {
    "Field Route Plans Trend": ("Field Route Plan", "route_date"),
    "Field Route Outcomes Trend": ("Field Route Visit Log", "recorded_at"),
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestNavigationContracts(unittest.TestCase):
    def test_route_doctypes_exist_and_fields_are_real(self):
        expected_fields = {"Field Route Plan": {"status", "route_date"},
                           "Field Route Visit Log": {"outcome", "recorded_at"}}
        for name, slug in ROUTE_DOCTYPES.items():
            with self.subTest(doctype=name):
                path = MODULE / "doctype" / slug / (slug + ".json")
                doc = load(path)
                self.assertEqual(doc["name"], name)
                self.assertEqual(doc["module"], "AV Field")
                available = {f["fieldname"] for f in doc["fields"]}
                self.assertTrue(expected_fields.get(name, set()) <= available)

    def test_cards_are_standard_and_permission_aware(self):
        for name, (doctype, filters) in CARDS.items():
            slug = name.lower().replace(" ", "_")
            path = MODULE / "number_card" / slug / (slug + ".json")
            card = load(path)
            with self.subTest(card=name):
                self.assertEqual(card["name"], name)
                self.assertEqual(card["document_type"], doctype)
                self.assertEqual(card["function"], "Count")
                self.assertEqual(card["type"], "Document Type")
                self.assertEqual(card["is_standard"], 1)
                self.assertEqual(json.loads(card["filters_json"]), filters)

    def test_charts_use_existing_doctype_date_fields(self):
        for name, (doctype, date_field) in CHARTS.items():
            slug = name.lower().replace(" ", "_")
            path = MODULE / "dashboard_chart" / slug / (slug + ".json")
            chart = load(path)
            with self.subTest(chart=name):
                self.assertEqual(chart["document_type"], doctype)
                self.assertEqual(chart["based_on"], date_field)
                self.assertEqual(chart["chart_type"], "Count")
                self.assertEqual(chart["is_standard"], 1)
                self.assertEqual(json.loads(chart["filters_json"]), [])

    def test_dashboard_references_standard_artifacts(self):
        dashboard = load(DASHBOARD)
        self.assertEqual(dashboard["name"], "AV Field Operations")
        self.assertEqual(dashboard["is_standard"], 1)
        all_cards = {r["card"] for r in dashboard["cards"]}
        all_charts = {r["chart"] for r in dashboard["charts"]}
        self.assertTrue(set(CARDS) <= all_cards)
        self.assertTrue(set(CHARTS) <= all_charts)
        for name in all_cards:
            slug = name.lower().replace(" ", "_")
            card = load(MODULE / "number_card" / slug / (slug + ".json"))
            self.assertEqual(card["is_standard"], 1)
        for name in all_charts:
            slug = name.lower().replace(" ", "_")
            chart = load(MODULE / "dashboard_chart" / slug / (slug + ".json"))
            self.assertEqual(chart["is_standard"], 1)

    def test_workspace_collections_and_render_blocks_match(self):
        w = load(WORKSPACE)
        self.assertEqual(w["module"], "AV Field")
        self.assertEqual(w["standard"], 1)
        blocks = json.loads(w["content"])
        block_cards = {b["data"]["number_card_name"] for b in blocks
                       if b["type"] == "number_card"}
        block_charts = {b["data"]["chart_name"] for b in blocks if b["type"] == "chart"}
        child_cards = {c["number_card_name"] for c in w["number_cards"]}
        child_charts = {c["chart_name"] for c in w["charts"]}
        self.assertTrue(set(CARDS) <= child_cards & block_cards)
        self.assertTrue(set(CHARTS) <= child_charts & block_charts)
        links = {(x.get("link_type"), x.get("link_to")) for x in w["links"]
                 if x.get("type") == "Link"}
        for target in ROUTE_DOCTYPES:
            self.assertIn(("DocType", target), links)
        self.assertIn(("DocType", "Address"), links)
        self.assertIn(("DocType", "Customer"), links)
        self.assertIn(("Dashboard", "AV Field Operations"), links)
        for entry in [x for x in w["links"] if x.get("type") == "Card Break"]:
            index = w["links"].index(entry)
            following = w["links"][index + 1:index + 1 + entry["link_count"]]
            self.assertTrue(all(x.get("type") == "Link" for x in following))

    def test_sidebar_and_dock_connectivity(self):
        sidebar = load(SIDEBAR)
        dock = load(DOCK)
        self.assertEqual(sidebar["module"], "AV Field")
        self.assertEqual(sidebar["standard"], 1)
        self.assertEqual(dock["app"], "av_field")
        self.assertTrue(any(x.get("link_to") == sidebar["name"]
                            and x.get("link_type") == "Sidebar" for x in dock["items"]))
        links = {(x.get("link_type"), x.get("link_to"))
                 for x in sidebar["items"] if x.get("type") == "Link"}
        for target in ROUTE_DOCTYPES:
            self.assertIn(("DocType", target), links)
        self.assertIn(("Dashboard", "AV Field Operations"), links)
        self.assertIn(("URL", None), links)  # Offline PWA uses /field


if __name__ == "__main__":
    unittest.main()
