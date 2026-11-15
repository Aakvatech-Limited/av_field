"""Static consistency checks for app-owned Frappe v16 navigation exports."""
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "av_field"
MODULE = APP / "av_field"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_navigation_exports_reference_real_records():
    sidebar = read(MODULE / "sidebar/av_field/av_field.json")
    workspace = read(MODULE / "workspace/av_field/av_field.json")
    dashboard = read(MODULE / "av_field_dashboard/av_field_operations/av_field_operations.json")
    dock = read(APP / "dock/av_field/av_field.json")

    assert sidebar["module"] == workspace["module"] == dashboard["module"] == "AV Field"
    assert dock["items"][0]["link_to"] == sidebar["name"]
    assert sidebar["standard"] == workspace["standard"] == dashboard["is_standard"] == 1

    for item in sidebar["items"]:
        if item.get("type") != "Link":
            continue
        if item["link_type"] == "Dashboard":
            assert item["link_to"] == dashboard["name"]
        if item["link_type"] == "Workspace":
            assert item["link_to"] == workspace["name"]
        if item["link_type"] == "DocType":
            assert item["link_to"] in {"Field Visit", "Field Order Request"}

    for row in dashboard["cards"]:
        slug = row["card"].lower().replace(" ", "_")
        doc = read(MODULE / f"number_card/{slug}/{slug}.json")
        assert doc["is_standard"] == 1
        assert doc["name"] == row["card"]
    for row in dashboard["charts"]:
        slug = row["chart"].lower().replace(" ", "_")
        doc = read(MODULE / f"dashboard_chart/{slug}/{slug}.json")
        assert doc["is_standard"] == 1
        assert doc["name"] == row["chart"]
        assert doc["based_on"] == "creation"

    blocks = json.loads(workspace["content"])
    assert {b["data"]["number_card_name"] for b in blocks if b["type"] == "number_card"} == {r["card"] for r in dashboard["cards"]}
    assert {b["data"]["chart_name"] for b in blocks if b["type"] == "chart"} == {r["chart"] for r in dashboard["charts"]}
    assert {r["number_card_name"] for r in workspace["number_cards"]} == {r["card"] for r in dashboard["cards"]}
    assert {r["chart_name"] for r in workspace["charts"]} == {r["chart"] for r in dashboard["charts"]}
