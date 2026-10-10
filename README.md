# AV Field

AV Field is an installable offline PWA for ERPNext field teams. Agents record customer visits and order requests on their device, then sync when a connection returns. Managers review requests in Frappe and create draft Sales Orders using ERPNext's current pricing and validation.

**Initial MVP — version 16.0.0, branch `version-16-hotfix`.** Requires Frappe and ERPNext 16. This is an independent app; it does not depend on `av_track`.

## What is included

- Customer visits with notes and optional, user-triggered GPS coordinates/accuracy.
- Order requests with multiple items and quantities in stock UOM.
- IndexedDB persistence: capture and reload the installed app while offline after initial preparation.
- A durable upload queue, per-record acknowledgement, retry backoff, duplicate detection, and visible rejected records.
- Account-separated local databases. An account change never uploads the previous account's queue.
- Complete, paginated offline snapshots of the customers and saleable items the user can read.
- Frappe Field Visit, Field Order Request, and Field Order Item DocTypes.
- Field Agent and Field Manager roles; agent records are readable only by their owner, subject to normal User Permissions.
- Manager action to create one draft Sales Order per request. ERPNext supplies prices/taxes and enforces its normal validation; the app never submits an order automatically.
- Device-record JSON export, local-storage clear controls, responsive layouts, and system light/dark theme.

## Preferred architecture

| Layer | Implementation | Responsibility |
| --- | --- | --- |
| Mobile UI | Installable PWA, native JavaScript modules | Visits, order capture, local history, sync controls |
| Device database | IndexedDB, separate database per ERPNext account | Durable local events, upload state, offline master snapshot |
| Offline shell | Scoped service worker + Cache Storage | Cache only public HTML/CSS/JS/icons; never cache API/login responses |
| Sync boundary | Versioned authenticated Frappe RPC | Validate each event, enforce permissions, acknowledge durable records |
| Field backend | Separate `av_field` Frappe app | Immutable capture records and manager review |
| Business authority | ERPNext | Customers, saleable items, companies, pricing, taxes, Sales Orders |

The MVP has no frontend build dependency and no CDN runtime dependency. Native browser modules keep the first offline implementation small and deployable through standard Frappe public assets. If the interface grows into route planning, merchandising, collections and van stock, migrate the UI to Vue 3 + TypeScript behind the same sync contract. A frontend framework does not replace the outbox and sync protocol.

Keep `av_track` integration optional: it can provide location/route data through an adapter later, without making a tracking app responsible for sales workflows. The backend and PWA can live in this single repository; a separate mobile repository is unnecessary for now.

See [architecture and sync contract](docs/architecture.md) for failure handling and expansion boundaries.

## Installation

On an existing Frappe/ERPNext v16 bench:

```bash
bench get-app --branch version-16-hotfix https://github.com/Aakvatech-Limited/av_field.git
bench --site your-site install-app av_field
bench build --app av_field
bench --site your-site migrate
```

Restart the bench's application processes using your hosting platform's usual procedure. Use HTTPS in production. Service workers and GPS require a secure browser context (localhost is allowed for development).

1. Assign **Field Agent** to agents and **Field Manager** to reviewers.
2. Give agents read access to **Customer** and **Item** using existing ERPNext roles or Role Permission Manager. The app does not grant broad access to those masters.
3. Use standard **User Permissions** to limit customer/territory/item visibility. Unrestricted readers download all customers/items they can see; there is no app-specific territory assignment engine yet.
4. Reviewers also need normal **Sales Order** create/read permissions and read access to the company, customer, and items they convert. Configure selling prices, defaults, accounts, warehouses, taxes, and any mandatory custom fields in ERPNext first.
5. Open `https://your-site/field`. It redirects to the installable shell at `/assets/av_field/pwa/index.html`.
6. Sign in, tap **Sync**, and wait for both the offline shell installation and customer/item download to finish. Use the browser's **Install app / Add to Home Screen** option where supported.
7. Open the installed PWA once in airplane mode and capture a test visit before issuing the device to an agent.

The service worker is deliberately scoped to `/assets/av_field/pwa/`; it does not take control of ERPNext Desk. For offline reopening, use the installed PWA or bookmark its actual `index.html` URL. The `/field` redirect itself requires the server to be reachable.

## Daily workflow

**Agent:** choose a customer → save a visit or an order request → see it as pending in Activity → reconnect with the app open → sync → open the acknowledged record in ERPNext if needed.

**Manager:** open **Field Order Request** in Desk → review customer/items/notes → click **Create Draft Sales Order** → select company and delivery date → review the resulting Sales Order → submit through the existing ERPNext controls. Conversion is serialized under a database row lock; repeating the action returns the existing Sales Order. Missing selling rates block conversion, rather than producing an unpriced order.

Captured records are append-only. Correct captured facts with a new request; do not silently overwrite an offline event. A rejected record retains its UUID and payload; fix its server-side prerequisite (permissions, enabled customer/item, etc.) and tap **Retry sync**. Agents cannot delete synced field records. Standard Frappe link checks prevent deletion of a linked Sales Order until an administrator deliberately resolves its request link.

## Offline behavior and limits

- First sign-in and master download require a connection. Offline capture uses the last successfully downloaded snapshot.
- Sync runs on startup, reconnection, window focus, a one-minute foreground timer, and **Sync now**. Keep the app open until it finishes. Closed-app background sync is not promised.
- Expired sessions pause uploads; signing in again preserves pending records. HTTP server outages retain offline access for the previously prepared account.
- Stale/revoked customer or item access is rechecked during upload. Validation failures appear in Activity; no financial record is created on the phone.
- Local data is readable by someone using the same trusted browser/device. Database separation prevents account mixing; it is not encryption or a remote device lock. Offline permission changes take effect when the app reconnects.
- Browser data can be evicted or cleared. Persistent storage is requested where supported, but it is not guaranteed. Export device records before clearing browser storage; this MVP exports backups but does not yet import them.
- GPS is a single opt-in capture, not continuous tracking or proof of physical attendance.
- Local records are not a cross-device history. Server records remain available in Desk; the MVP does not pull historical visit/order events back onto new devices.

## Scope remaining

Planned modules: routes and daily beat plans, check-in/out duration, merchandising surveys/photos, collection receipts and payment reconciliation, van stock/deliveries, cached customer-specific indicative prices, manager dashboards, and an optional native wrapper if background location becomes mandatory. These require their own permissions, offline conflict rules, and acceptance tests.

## Development and validation

```bash
python -m unittest discover -s tests -v
npm ci
npm test
npx playwright install chromium --only-shell
npm run test:browser
```

Contract tests cover input validation, account-specific operation IDs, stable payload hashes, queue retries, partial master downloads, and authentication expiry. The browser suite uses real Chromium, service workers, and IndexedDB against a deterministic HTTP API fixture. CI runs both suites, checks packaging, and rejects raw SQL. Browser tests are not a substitute for installing the app on a real v16 site.

Before production use, complete the [v16 site acceptance checklist](docs/acceptance.md), especially agent permissions, actual ERPNext prices/taxes, concurrent conversion, and offline reload on the target phones.

## License

MIT. Copyright Aakvatech Limited.
