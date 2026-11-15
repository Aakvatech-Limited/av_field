# Sales route planning (Skynamo-style field operations)

AV Field now supports a recurring weekly call cycle, individual outlet visit frequencies, manager-published daily route plans, an assigned salesperson's offline route, an ordered driving-directions link, and recorded visit outcomes.

## Master setup

1. Maintain **ERPNext Customer**, **Territory**, and **Address** normally.
2. Create **Field Route Zone** for territories or sales areas.
3. Create a **Field Customer Outlet** for each physical site. Multiple outlets may reference the same Customer. Set the assigned ERPNext User, zone, coordinates (if known), visit frequency in days, expected visit duration, preferred day/time window, priority and directions/instructions. Outlets without GPS coordinates remain in the stop list, but cannot produce map navigation.
4. Create **Field Call Cycle** for a salesperson. Add **Field Call Cycle Stop** rows for each weekday, in a manager-controlled sequence. Only active outlets assigned to the selected salesperson may be used. The planned time and visit purpose may vary by stop.
5. Use **Generate Daily Route** on the saved Call Cycle, select the date and **Publish to Salesperson**. The backend excludes outlets visited more recently than their configured frequency (based on a previous Done log). If no outlets are due, no empty plan is created. Managers can also create a Field Route Plan manually in Desk.

## Statuses and action details

| Status | Meaning | Required detail |
| --- | --- | --- |
| Pending | Planned, no outcome captured yet | None |
| Done | Visit took place | Action taken, notes and next action encouraged |
| Skipped | The salesperson deliberately bypassed this stop | Reason |
| Not Done | Visit could not be completed | Reason |
| Postponed | Visit rescheduled to another date | Reason and postponed date |

Each outcome can record action taken, next action, next-action date, optional GPS/accuracy and device timestamp. An outcome is stored as an immutable **Field Route Visit Log** with a UUID operation ID, then updates the corresponding stop's current status. Retrying the same synced operation returns the original acknowledgement. Agent field updates are accepted only for a route assigned to that agent and only for a currently Pending stop.

**Important:** A Postponed outcome does **not** automatically add a stop to another plan. Managers must put the postponed visit into an appropriate subsequent route. Published plans do not autonomously change order after device download.

## Salesperson workflow

1. Install the PWA at `/field` and sign in as **Field Agent**.
2. Sync online before travel. The PWA caches only the signed-in person's published route plans and assigned outlet locations, in addition to customer/item masters.
3. Open the new **Routes** tab. Follow numbered stops. Use **Open ordered directions** for multi-stop driving guidance or **Navigate to outlet** for an individual stop. Google Maps road directions require connectivity; an offline road routing engine is **not** provided.
4. At a stop, choose **Record outcome** and select Done / Skipped / Not Done / Postponed, with reason and action details. Optional GPS is captured only by tapping the control. The outcome is committed to IndexedDB before the UI confirms it.
5. Reconnect and Sync. The server checks agent assignment, applies the outcome, and sends back the latest plan snapshot. Rejected operations remain in Activity for review/retry.

Route planning is independent of existing immutable **Field Visit** and **Field Order Request** events. Recording a route outcome does not implicitly create a Field Visit or a Sales Order. Use the Visit/Order screens when those records are required.

## Manager review

Use **Field Route Plan** list filters for date, salesperson, status, and zone. Review current stop outcomes and the related **Field Route Visit Log** records for a detailed action trail. Before assigning handsets, verify role permissions and ERPNext User Permissions. Direct Desk reads by field agents are owner-restricted; the scoped PWA endpoints fetch only routes/outlets assigned to the authenticated user.

## Current boundaries

- Route ordering is controlled by the manager's call-cycle sequence. Google Maps presents the ordered driving stops in groups; the app does **not** claim real-time road-network optimization, traffic ETA or offline turn-by-turn routing.
- Preferred visiting windows and outlet priority are stored for manager planning, but do not currently run a capacity optimizer.
- Postponements do not automatically regenerate schedules or send notifications.
- Route status is separate from CRM sales outcomes and transactional orders; future work can link outcomes to opportunities, samples, collections, merchandising checks and invoices.
- GPS on the handset is optional, permission-based, and cannot by itself prove physical presence.
- Full on-device acceptance testing on a real Frappe/ERPNext v16 site remains necessary before field rollout.

## Site QA checklist

- Install/migrate the app; confirm all seven DocTypes appear in the AV Field module.
- Create two agents, a manager, two zones and outlets assigned to different agents.
- Generate routes for both; verify a different agent cannot download or change the other's route.
- Download a published route, go offline, record each outcome including postponed date and GPS, reload, and reconnect.
- Repeat one upload with the same UUID; check one log record and one status change.
- Attempt two different updates to the same stop; the later attempt should be rejected after the first resolves it.
- Verify a completed visit suppresses a fresh plan before visit_frequency_days have elapsed.
- Verify unavailable GPS does not block saving; test multiple consecutive map-direction groups.
- Confirm existing visits, orders and Sales Order conversion continue working.
