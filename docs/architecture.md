# Architecture and sync contract

## Separate Frappe app with an offline PWA

`av_field` owns field capture and its sync boundary. ERPNext owns business masters and financial/stock transactions. A network request is never required to complete a prepared device's local capture; an IndexedDB transaction must commit before the UI reports success.

The first UI uses native JavaScript modules so a standard `bench build --app av_field` asset setup is sufficient. A future Vue/TypeScript UI can reuse the same API and storage contract. No custom Node server, shared-browser API key, or second database service is required.

## Capture contract v1

Each operation has `version: 1`, a UUID `id`, `kind` (`visit` or `order`), timezone-aware `recorded_at`, and `payload`. The server normalizes the timestamp to UTC. `recorded_at` records the device clock and is not trusted proof of attendance; Frappe's `creation` is server receipt time.

Visit payload: customer, notes, optional latitude/longitude/accuracy. Coordinates must be paired. Zero coordinates are valid. Stored precision is latitude/longitude 8 decimals, accuracy 2 decimals. Accuracy zero indicates unknown if coordinates were supplied without accuracy.

Order payload: customer, notes, 1–100 unique `{item_code, qty}` entries. Quantities use stock UOM and are positive, finite, at most 1,000,000, at 6 decimals. Notes are limited to 5,000 characters. Owner, rates, status and Sales Order references cannot be provided in the payload.

## API

All methods require an authenticated Field Agent, Field Manager, or System Manager.

| Method | HTTP | Contract |
| --- | --- | --- |
| `av_field.api.context` | GET | Current user, CSRF token, contract version; never persist token on the device |
| `av_field.api.references` | GET | `kind=customers/items`, optional `after`; at most 200 rows and next cursor |
| `av_field.api.push` | POST | One operation; acknowledgement with id, DocType, name, duplicate flag |
| `av_field.api.make_sales_order` | POST | Manager-only request name, company, delivery date; returns draft SO name |

Authentication uses the same-origin Frappe session cookie. POST requests require Frappe's CSRF token. No CORS relaxation and no secrets embedded in the app.

Reference reads use `frappe.get_list`, so role and User Permissions apply. The app downloads every page into a temporary in-memory snapshot, then replaces the previous snapshot in one IndexedDB transaction. Partial downloads do not truncate the working offline catalogue. A full snapshot removes inaccessible/deleted masters on the next successful sync. It is not a transactionally consistent snapshot across all database pages; an active master rename/edit can be reflected on the next refresh.

## Duplicate safety and transaction boundaries

A field document's primary key is `FIELD-` plus SHA-256 of `user:UUID`. Its canonical payload fingerprint is stored with the document. Repeating the same operation for the same user returns the existing acknowledgement; reusing the ID with different data is rejected. A savepoint handles simultaneous duplicate insertions. No explicit commit occurs in the push API; Frappe commits a successful POST before responding and rolls back a failed POST.

The device keeps a record pending until it receives a matching acknowledgement. A dropped response can be retried with the same UUID. Transport is at least once, while the unique document primary key prevents duplicate effects within each field record type. UUIDs are generated once per capture, not once per upload attempt.

Conversion locks the Field Order Request row using `frappe.qb` with `for_update`, checks role/document permissions and enabled masters, then creates the draft Sales Order and updates the request link in the same transaction. A ContextVar guard permits only this server action to add the link to an immutable capture record. An API/REST client cannot bypass immutability by supplying a document flag. Prices/taxes come from standard ERPNext methods; no financial posting occurs offline.

A submitted/cancelled or deleted Sales Order is not automatically recreated. Resolve the existing request link through a deliberate administrator correction if business policy requires replacement.

## Queue states

| State | Meaning | Next action |
| --- | --- | --- |
| pending | Local committed event; no durable matching server acknowledgement yet | Retry on foreground sync; transient errors use capped exponential backoff |
| synced | Matching server acknowledgement stored locally | Keep as local history; server is authoritative |
| rejected | Server validation failed | Display error; repair prerequisite and retry exact payload/UUID |

Authentication/permission errors pause sync without dropping the queue. Transport errors, HTTP 408/429 and 5xx remain pending. A validation failure does not stop later records. A malformed/mismatched acknowledgement is transient and cannot mark a record synced.

Web Locks serialize foreground sync across tabs where supported. On browsers without them, server duplicate handling remains authoritative. Background Synchronization is intentionally not required: mobile browsers can suspend/terminate background work, and support varies.

## Account and cache boundaries

IndexedDB database names include the authenticated account. The remembered offline identity is a local pointer, not an authentication token. Online identity verification always precedes uploading. A changed online account locks the current screen; reload opens a different database. Records belonging to the old account are retained and become available again only when it is the active account. Offline operation assumes the prepared trusted device belongs to its remembered user.

The service worker controls only its public static PWA asset directory. It intercepts no `/api`, `/login`, `/app`, or private-file request. The shell cache contains no session/CSRF/user data. On releases, bump the shell cache version; fetch updated shell assets with HTTP cache reload and activate after old tabs close, to avoid interrupting local saves.

## Extension rules

- Append new capture kinds with versioned validation and durable UUID handling. Do not expose arbitrary DocType writes.
- Plan routes/assignments online; pull only authorized records. Adding server-change feeds requires monotonic cursors, deletions/tombstones, and snapshot recovery.
- Store photos as local blobs with a separate upload queue and acknowledgement; do not base64 them into the operation request.
- Payment captures must become reviewable collection records, with server-authoritative currency/rates and bank reconciliation rules; do not create Payment Entries directly from unverified phone payloads.
- Van stock requires warehouse/user assignment, inventory reconciliation, and explicit handling for conflicts; cached stock cannot guarantee availability.
- Pricing shown offline must be labelled indicative and timestamped. The server must recalculate commercial documents.
- Continuous background location may justify a native wrapper. Keep the backend contract independent of that decision.
