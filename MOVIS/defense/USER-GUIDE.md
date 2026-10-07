# User roles and operating guide

| Action | Administrator | Operator | Viewer |
|---|---|---|---|
| View inventory and reports | Yes | Yes | Yes |
| Android photo capture/review | Yes | Yes | No |
| Confirm incoming addition or complete count | Yes | Yes | No |
| Edit total stock with reason | Yes | Yes | No |
| Record/inspect/restock returns | Yes | Yes | No |
| Manage items, locations, stock registrations and accounts in Android | Yes | No | No |
| Change own password / revoke own sessions on web | Yes | Yes | Yes |

Permissions are enforced by the backend; hiding a button is not the permission
check. Assign individual accounts rather than sharing one administrator login.

## Install and sign in

Use MOVIS-Defense.apk, the signed 0.5.0 testing build, on Android 8.0 or later.
Transfer the APK, open it and permit installation from the specific Files/browser
app when prompted. Prefer updating the existing MOVIS installation; its signer
must match. If Android reports a signature conflict, uninstall the old application
only after preserving any unsent photo work; hosted records remain on the server.
The app opens https://movis-1fxf.onrender.com automatically. Use your existing
private hosted account. No account password, database URL or model is in the APK.

The website is opened at the same HTTPS URL. After secure-cookie upgrade sign in
again if necessary. Refreshing preserves an active cookie session. Change your
password under Account security, or enter the current password to sign out all
devices. That revokes Android sessions too. Web signs out after 15 minutes without
interaction; the server separately expires sessions after 30 minutes without API
activity, with a maximum eight hours after sign-in. Polling is API activity, not
proof of a user physically present. Android requests a fresh login after a 401.

## Register a warehouse

Administrator: Android account menu -> Manage warehouse. Create locations, SKUs,
item names and exact YOLO class labels. Register each item at each intended location;
registration starts at zero. Establish the opening balance with a verified manual
total and an honest reason. Do not leave demo stock as operational records. For a
fresh real database set MOVIS_SEED_DEMO=0; this does not remove already seeded data.

## Incoming goods

Android Photo -> Incoming goods. Select destination, take/select a photograph and
Analyze photo. Inspect boxes, labels, confidence and visible counts. Correct missed
items and false detections. Select incoming items, enter positive quantities and
receipt/reason, review the confirmation and Add. Existing stock increases; taking
or analyzing a picture alone never changes stock. Discard leaves inventory unchanged.
Photographing units already included in stock and adding them would double-count;
use Complete count instead for reconciliation.

## Complete count and manual edit

Android Photo -> Complete count. Select the precise location and analyze a photo.
Choose an item to verify. Physically count all its units at that location, including
units outside the image or hidden from view. Enter that TOTAL, reason and the
complete-count checkbox. Review previous, verified and difference, then confirm.
A changed stock version requires a new scan and verification. One successful
reconciliation clears the photo; rescan for another item.

For a manual total, choose Edit quantity in Android or web inventory. Specify a
nonnegative TOTAL and reason. The stored version prevents silently overwriting a
concurrent change. Manual totals and returned goods produce distinct history entries.
No workflow is a license to guess unseen stock.

## Returns and reports

Android Returns: record item, destination, positive quantity and reason. Goods
remain unavailable while pending inspection. After actual inspection choose
accepted or damaged. Only accepted goods can be restocked after explicit suitability
confirmation. Repeated restock requests do not increase stock twice. Returns do
not subtract an original sale or shipment; outbound-sales/order handling is outside
this capstone's implemented scope.

Web Overview shows totals/stock warnings; Inventory provides filters and manual
edits; Returns monitors statuses; Stock activity shows movements, adjustments and
read-only Android scan history. Android Reports includes inventory, scans, adjustments,
returns, return events and movements. Exported CSV text is neutralized when it could
be interpreted as a spreadsheet formula. A committed scan entry means some verified
stock action was saved, not that all visible detections were proven correct.

## Troubleshooting

| Symptom | Safe response |
|---|---|
| First request is slow | Allow the hosted service to wake up; confirm internet and /health |
| Invalid username/password | Use the existing hosted account, not a local demo login; changing Render bootstrap variables does not reset it |
| Timeout after saving | Refresh stock/history first. Retry unchanged quantities/reason with the same operation rather than inventing a new receipt |
| Stock changed / conflict | Refresh; recount and take a new scan for reconciliation |
| Unknown class | Ask admin to register the exact model class and location stock; do not silently map it to a different item |
| Synthetic banner | Mode is demo; no warehouse recognition has occurred |
| Model startup failed | Check weights path/checksum, YOLO image dependencies and memory; no automatic fake inference fallback |
| Session expired | Sign in again; password changes/all-device logout also invalidate old Android sessions |
| APK will not install | Check Android >=8, APK transferred completely, signing compatibility and installation permission |
| Computer off and app fails | Verify Render health on mobile data and the hosted URL; deployment is internet-dependent, not offline |
