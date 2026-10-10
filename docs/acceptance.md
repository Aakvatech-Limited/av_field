# v16 deployment acceptance

The lightweight tests and fixture browser suite do not run a full ERPNext database. Complete these checks on a test bench before production rollout.

1. Install on a clean Frappe/ERPNext v16 site. Verify DocTypes and the two field roles exist, `/field` redirects, assets load, and the browser reports an active service worker.
2. Create two Field Agent users with Customer/Item read permissions and different User Permissions. Confirm reference downloads respect those restrictions, and each user can read only their own captures. Test unauthorized Customer/Item IDs against the API directly.
3. Download masters, install the PWA, enable airplane mode, reload, save a visit with/without GPS and a multi-item order. Close/reopen while offline. Verify device records survive. Test actual Android/iOS target browsers.
4. Reconnect and sync. Verify customer/item permissions and disabled status are checked again. Confirm each pending operation becomes exactly one server document. Drop an acknowledgement and replay the same operation UUID; verify a duplicate acknowledgement. Submit altered data under the same UUID; verify rejection.
5. Revoke a user's field role/session and attempt sync. Confirm uploads stop without losing pending records. Log in as another user; confirm no old account records are displayed or uploaded. Return to the original user and resume.
6. Modify/delete masters while downloading pages; verify a failed download leaves the previous snapshot intact and a subsequent completed snapshot removes inaccessible records.
7. Give a Field Manager Sales Order permissions. Configure a priced saleable item, company, selling defaults/accounts/warehouses/taxes. Convert a request into a draft Sales Order. Verify stock UOM quantities, rates, pricing rules, currency, tax totals, custom validations and delivery date. Submission must remain manual.
8. Convert the same request concurrently from two sessions; confirm only one Sales Order is created and both responses return it. Force a conversion validation failure; confirm neither an order nor request link commits. Missing rates must block conversion.
9. Attempt edits through standard REST/Desk as both an agent and manager; captured facts must remain immutable. Attempt to supply `flags.allow_conversion`; it must not bypass the server guard. Verify notes/customer labels containing HTML render as text in the PWA.
10. Inspect Cache Storage: only public shell assets are stored. No API/login/private response may be cached. Verify service worker scope does not control Desk. Install a new shell version with existing tabs open, close them, and reopen to verify the update does not lose IndexedDB records.
11. Test quota/storage denial and interrupted writes: UI must not claim a local save succeeded if the IndexedDB transaction did not commit. Export local records and verify clearing is blocked while unsynced records remain.

Record the test site versions and target devices with sign-off. Do not describe the app as production-validated until these checks have run.
