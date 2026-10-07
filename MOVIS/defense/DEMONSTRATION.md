# Defense demonstration and panel questions

## Preparation and truth statement

Deploy the updated source, install the 0.5.0 APK, and perform the actual-device
acceptance checks before presenting. Use an isolated demonstration warehouse or
clearly marked test item/location. Obtain permission before using real photographs
or customer return information. Keep passwords, tokens and database URLs off screen.
If no trained model is installed, start by stating: this demonstration uses sample
detections to demonstrate verification and stock workflows; recognition accuracy
has not been evaluated. Do not refer to demo processing time as YOLO inference time.

## Repeatable live demonstration

1. Show website and Android using https://movis-1fxf.onrender.com. With the computer
   server stopped, preferably use mobile data to prove the cloud connection. Keep
   a backup demonstration video if free hosting is temporarily unavailable, and
   identify any video as a recording rather than a live test.
2. Admin registers a unique DEFENSE item and DEFENSE location with zero stock.
   Use a class actually in the trained model; for demo choose an explicitly test
   class. Record a manually verified opening total of 10 with a reason.
3. Android Incoming goods: take/select a still photograph. Show detections, correct
   a quantity to 2, and demonstrate Discard first. Website remains at 10.
4. Analyze a new photo, verify 2 new incoming units and confirm Add. Refresh the
   website: quantity becomes 12. Show adjustment reason/user/time and movement.
5. Demonstrate complete count with a fresh scan. Physically verify a total of 11;
   review previous 12, verified 11, difference -1. Confirm only after checking the
   complete-count declaration. Website becomes 11 with full history.
6. Record a return of 3. Website still shows available stock 11 while pending.
   Inspect and accept; still 11. Confirm suitability/restock: website becomes 14.
   Show that a repeated status request does not add another 3 units.
7. Show a viewer account: inventory/reports are visible; changes are forbidden by
   the server. Demonstrate stale stock rejection using two edit sessions if rehearsed.
8. Open Stock activity -> scan history/CSV. Explain pending review versus committed
   stock actions and demo versus YOLO mode. The website has no photo upload screen.
9. On a TEST account, change the password or Sign out all devices. Show the other
   session needs to sign in again. Do not risk losing the only administrator login.
10. Present the test matrix and outstanding research/device checks honestly.

Do not repeat incoming additions with new receipt keys as a retry demonstration;
that represents a new operation. The automated tests prove exact-request retries.
Do not modify real production stock solely to make a demo look successful.

## Likely panel questions

**What makes stock adjustment automated?** After authorized verification, the
server calculates verified minus recorded, updates stock transactionally and
creates history. Detection does not authorize the update; physical handling is manual.

**Can one photo count everything in a warehouse?** No. It counts visible trained
classes only. Hidden units, overlap, lighting and distance can reduce detection.
Complete-location reconciliation requires manual verification of unseen stock.

**What is the difference between addition and reconciliation?** Addition increases
the current total by NEW incoming units. Reconciliation sets the total after a
complete physical count. Separate UI choices and backend restrictions avoid mixing them.

**Why YOLO?** It supplies bounding boxes, labels and confidence for multiple visible
objects from one photograph. The project's actual class-level and counting results
must justify its suitability; no accuracy result exists yet for the warehouse.

**Where does processing happen?** Android captures/compresses/orients the image;
Render's Python backend runs the model and validates actions; Neon stores records.
The web monitors the same database. Model weights are separate from inventory data.

**What if the connection fails after a save?** A timeout does not prove the save
failed. Refresh records; identical operation keys return the original result.
Transactions, stock versions and scan/return uniqueness protect against duplicates.

**What if two personnel count the same stock?** Snapshot versions reject stale
reconciliation. Database transactions serialize the read/check/write operation.
The current global write lock favors correctness for a small warehouse over scale.

**How are damaged returns handled?** They remain outside available stock. Only an
accepted, inspected return with suitability confirmation is restocked once.

**How do you secure it?** Roles are enforced server-side; hashes, HTTPS, HttpOnly
web cookies, CSRF origin checks, persistent attempt limits, session expiry/revocation,
bounded uploads, safe CSV exports and parameterized SQL protect common paths.
MFA, edge rate limiting and tamper-evident logs are not claimed as implemented.

**Why is the computer no longer needed?** Cloud hosting serves both clients. A
computer was needed to build/deploy, but not to run each request. Internet and
service availability are still needed; there is no offline synchronization.

**Have users accepted it?** Not measured yet. Show the planned tasks/questionnaire,
participant selection and unfilled results rather than an invented acceptance score.

**Is it ready for final defense?** Software corrections and tests are evidenced.
Final research validation still requires a selected warehouse, trained/tested model,
actual-device/cloud workflow checks, usability study and adviser-approved manuscript.
