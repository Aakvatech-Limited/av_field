# AV Field contributor rules

- `version-16-hotfix` targets Frappe/ERPNext >=16,<17. Keep package version major aligned with the branch.
- This is an offline field application. Local capture must commit atomically before showing success, and upload retries must keep the original UUID and immutable payload.
- Preserve account separation, normal Frappe document permissions and User Permissions. Do not use `get_all` or `ignore_permissions` to deliver mobile master data.
- Use `frappe.qb` or document APIs. No raw SQL.
- ERPNext calculates commercial documents. Do not trust device-provided rates, taxes, ownership or financial status.
- Never cache private API/auth responses in the service worker. Keep it scoped to the PWA asset directory.
- Do not persist API keys/session secrets/CSRF tokens in localStorage or IndexedDB.
- Captures are append-only. Financial posting and corrections require explicit server workflows.
- Run contract tests, queue tests and real browser offline tests for changes to sync/storage. Install on a v16 test site for schema, permission or ERPNext conversion changes.
- Keep README and architecture/acceptance documentation aligned with implemented scope and actual verification. Do not imply background sync, continuous tracking or full SENRI feature parity.
- Bump the shell cache version when shell files change for a release. Preserve existing device queues during upgrades.
