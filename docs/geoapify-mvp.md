# Geoapify sales route optimization — ERPNext Customer + Address

## Production setup (Frappe/ERPNext v16)

1. Install/migrate `av_field` v16.0.4. The app creates additive custom fields on **Customer** and **Address** if they do not already exist. It never replaces existing Address or Sales Team data.
2. On each **Customer**, set **Field Salesperson (User)** to the real Frappe login used by the field salesperson. Set **Field Visit Frequency (Days)** (default 7); zero means visit frequency filtering is disabled. ERPNext Sales Team remains available for commission allocations.
3. On each physical **Address** linked to that Customer, enable **Include in Field Sales Routes** and place exactly one Point marker in **Field Sales Location** (Geolocation/GeoJSON). Set preferred visit times, visit duration, priority and instructions as needed. The same Customer may have many independent Address locations.
4. Create a **Field Route Optimization Settings** singleton, enter a Geoapify Route Planner API key (Password field), enable the provider, choose a starting **Address** with one point, and specify working hours, traffic model, maximum stops and baseline daily-credit budget.
5. As a **Field Manager**, open the **Field Route Plan list**, choose **Generate Optimized Route**, select the salesperson User and date, and decide whether to publish immediately. The app gathers all visit-enabled, assigned Customer Addresses due by visit frequency. It sends only coordinate, stop-duration, time-window, priority and anonymous job IDs to Geoapify. Customer identities and API keys are not sent in jobs; the key stays server-side.
6. Review the saved route, estimated distance and driving time. Publish the route to the salesperson. The PWA downloads the assigned route and linked Address points, then supports offline Done / Skipped / Not Done / Postponed outcomes.
7. Google Maps driving links open on demand; they are not an offline turn-by-turn road navigator.

## Provider contract

- Endpoint: `POST https://api.geoapify.com/v1/routeplanner`, JSON `agents`, `jobs`, `mode: drive`.
- Auth: secret API key configured in the single settings record; server-side POST only. Do not embed keys in PWA assets or logs.
- GeoJSON Point coordinates are `[longitude, latitude]` (Geoapify also expects that order). Google Maps URL coordinates are `latitude,longitude`.
- Only one unambiguous Point per Address is accepted. Invalid/missing or multi-point addresses fail route planning rather than silently route elsewhere.
- Response must contain the complete set of requested job IDs, with no duplicates or unassigned jobs. Partial plans fail; the user can choose a smaller route and retry.
- The free-tier budget guard estimates credits using `n × min(n, 10)`, where n is unique start + visit locations. This is a **baseline estimate**, not authoritative billing. Distance/avoidance surcharges, failed attempts and concurrent requests can still consume extra provider credits. Monitor the Geoapify dashboard directly.
- If Geoapify fails or credits are insufficient, **existing manual Call Cycle / Route Plan entry remains available**. No inaccurate straight-line route is silently presented as an optimized driving route.
- Optimization is one salesperson per request, max 100 stops (configurable smaller default 20). Time windows, visit duration and priority are provided to Geoapify; all eligible visits must fit or the planner rejects the request.

## Upgrade compatibility

This update intentionally **retains** `Field Customer Outlet`, old `outlet` links and historical logs to avoid destructive migration. New address-based plans populate `customer` and `address`; old plans keep working with the legacy outlet field until reviewed. There is no automatic migration of outlet coordinates into Address because the two records may differ.

Manual recurring `Field Call Cycle Stop` rows should now select Customer + Address (legacy Outlet remains available for existing rows). New optimized routes are independent of manual call cycles.

## Security and UAT

- Assign salesperson Users with Field Agent role and managers with Field Manager role.
- Only managers can optimize. The API always checks ownership/assignment via Customer and Address Dynamic Link before routing.
- The offline snapshot includes locations for Customers assigned to the authenticated account, not all addresses.
- Test with two field users and overlapping customer names; verify no cross-account route or location leakage.
- Test: one customer/multiple addresses, invalid coordinates, no selected addresses, duplicate addresses, all jobs assigned, one unassigned job, work time windows, no API key, API timeout, free quota budget, and repeated sync UUID.
- Confirm the Geoapify provider actually optimizes a Dar es Salaam route using your own test key and representative GPS locations. This repository work does **not** include a live provider call because no API key was supplied.
- Before deployment run `bench --site <site> migrate`, `bench build --app av_field`, Python tests, JS/browser tests, and a real-device offline acceptance run.

## Pricing reference

[Geoapify Route Planner](https://apidocs.geoapify.com/docs/route-planner/) and [pricing](https://www.geoapify.com/pricing/). As of November 2026 the public free plan advertises 3,000 credits per day; verify current provider terms before deployment.
