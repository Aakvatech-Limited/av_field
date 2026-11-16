# AV Field route navigation and analytics (16.0.5)

Follow-up to merged Geoapify functionality. The AV Field Sidebar, Workspace and Operations Dashboard are extended; Dock already points to the valid AV Field Sidebar and is reused.

## Navigation coverage

| Area | Targets | Audience |
| --- | --- | --- |
| Daily operations | Field Route Plan; Field Call Cycle; Field Route Visit Log | Manager; log is manager read-only |
| Masters | Field Route Zone; ERPNext Customer; ERPNext Address | Manager, subject to ERPNext permissions |
| Settings | Field Route Optimization Settings (Geoapify) | Manager/System Manager |
| Dashboards | AV Field Operations | Existing Dashboard expanded |
| Offline app | /field | Field Agent/Field Manager |
| Existing operations | Field Visit; Field Order Request; Sales Order; Item | Existing permissions |

Legacy Field Customer Outlet remains for historical links but is intentionally not promoted in navigation. Field Route Stop, Field Call Cycle Stop and Field Order Item are child tables and not standalone list targets.

## KPI definitions

| Measure | Source | Formula | Date basis |
| --- | --- | --- | --- |
| Field Routes Total | Field Route Plan | Count all readable plans | lifetime |
| Field Published Routes | Field Route Plan | Count status = Published | lifetime |
| Field Route Outcomes Total | Field Route Visit Log | Count all readable outcome logs | lifetime |
| Field Postponed Visits | Field Route Visit Log | Count outcome = Postponed | lifetime |
| Field Route Plans Trend | Field Route Plan | Weekly Count | route_date, Last Quarter |
| Field Route Outcomes Trend | Field Route Visit Log | Weekly Count | recorded_at, Last Quarter |

These metrics use existing standard Document Type Number Cards and Count charts (no custom Chart Source). They do not equate a visit log to a customer visit: skipped and postponed outcomes also produce log rows. Pending stops are not counted by this release, since the pending state is stored on a child table and would require a permission-aware custom source.

All new Cards and Charts use is_standard=1 so they may be embedded in the existing standard AV Field Operations Dashboard. Charts and cards are also declared in the Workspace child collections and content blocks. Permissions on source DocTypes still govern data; Workspace visibility does not confer manager access.

## Export paths and upgrade

- Sidebar: av_field/av_field/sidebar/av_field/av_field.json
- Workspace: av_field/av_field/workspace/av_field/av_field.json
- Dock (unchanged): av_field/dock/av_field/av_field.json
- Dashboard: av_field/av_field/av_field_dashboard/av_field_operations/av_field_operations.json
- Number Cards: av_field/av_field/number_card/<slug>/<slug>.json
- Charts: av_field/av_field/dashboard_chart/<slug>/<slug>.json

Export structure reuses checked-in AV Field v16 standard artifacts. Do not overwrite user- or site-level navigation arrangements.

## Acceptance checklist

1. Run bench --site SITE migrate and bench build --app av_field on a Frappe v16.50+ development site.
2. Verify record existence independently: frappe.db.exists('Sidebar','AV Field'); frappe.db.exists('Workspace','AV Field'); frappe.db.exists('Dashboard','AV Field Operations'); frappe.db.exists('Number Card','Field Published Routes'); frappe.db.exists('Dashboard Chart','Field Route Plans Trend').
3. Validate the Dashboard's Card/Chart child entries, Workspace chart/card collections and rendered content. Open Dashboard View (not the Dashboard config form).
4. As Field Agent, Field Manager and System Manager, check links and underlying role permissions. Manager-only settings/log records must not disclose data to agents.
5. With representative records, verify status filters, trend date fields, all-time counts, zero-record handling, no double counting and visible values.
6. Verify desktop Dock visibility for a new account and a user with a customized arrangement; do not reset user preferences.
7. Run Python unit tests, compile checks and the repository's actual CI. Confirm frappe-maintenance central CI onboarding separately.

Static source integrity is tested by tests/test_navigation_contract.py. Repository CI does not prove successful database import or runtime rendering; leave the PR draft pending site validation.
