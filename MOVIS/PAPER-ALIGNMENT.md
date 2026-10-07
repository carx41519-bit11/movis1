# MOVIS 0.6.0 alignment with chapter123.pdf

Reference: supplied Chapter 1 to 3 paper, particularly pages 2-12, 33-40, 48-49 and algorithms on pages 54-61. This paper replaces the previously supplied CookAI document for this task.

## Implemented changes

| Paper requirement | Implementation |
| --- | --- |
| Three rice products, 25 kg sacks, no storage-location tracking | rice_products balances with one sack as one unit; new screens have no location selector |
| Administrator web and limited staff Android interfaces | Owner decisions and account controls on web; stock, five permitted action types, pending cases and recent actions in Android |
| Choose action before camera | Open action selects stock-in, stock-out, count, return or damage and chosen products before capture |
| New images only, rear camera at 1x | CameraActivity captures inside MOVIS; no gallery import or zoom control |
| Captured Images, enlargement, review, deletion and retaking | Per-action retained images, raw boxes/scores, separate checked rice counts, delete then Add more images |
| Multiple images and products | Server derives per-product totals from checked, retained images and reasoned additional checked entries |
| No changes during image review | Scanning and Save scan never post stock movements |
| Verified stock-in and stock-out | Atomic changes across all products; entire request rolls back if stock is insufficient or a required save fails |
| Partial count, Finish count and separate correction | Open images preserve partial progress; Finish count saves comparisons only; authorized adjustment checks full coverage and versions again |
| Latest stock and physical zero confirmation | Per-product stock versions; baseline refresh resets image verification; zero counts need explicit physical confirmation |
| Return and damage owner review | Pending case records; administrator inspection decisions with partial quantities and restock/repack/dispose histories |
| Prevent double additions or deductions | Unique request outcomes; remaining case quantities; stocked/unstocked disposition matrix; action/image locks |
| Original detection records and evaluation | Raw labels, boxes, confidence, processing time and model hash remain separate from corrected counts; training labels and count-metric helper prepared |

## Verification and limits

The new workflow has 16 SQLite regression tests for combined images, deleted images and late results, concurrency, unchanged retries, all-or-nothing stock-out, count permissions, stale versions, zero confirmation, return decisions, partial decisions, account privacy and storage-failure rollback. The full suite also retains authentication, session, model-loader and historical domain checks. See VALIDATION-0.6.0.txt for the final run results.

Browser form and layout checks used isolated data exported from the domain service with intercepted requests. Correction, owner decision and permission forms sent the expected payloads without JavaScript errors. Desktop and 390px mobile layouts were inspected. Network HTTP behavior is tested separately through the backend suite; a hosted browser-and-phone run is still required.

Android sources compile against API 35 with Java 17 output, and the APK signature is verified. Because the Windows sandbox interrupted native ZIP finalization, packaging reconstructed the resource ZIP from checked local entries before signing. Normal Gradle/Android Studio builds remain to be verified. The camera, permission prompts, orientation, rear-lens selection and stock synchronization still require a real phone test. This is a debug-signed test APK, not a store release.

No trained weights or labeled rice images were provided. The user will train later. Demo results are synthetic. No real precision, recall, mAP, count accuracy, warehouse acceptance, or speed advantage is claimed.

## Data and deployment

No production records were changed. Back up the hosted database before deployment. Existing accounts and legacy inventory/history tables remain intact. On first new-backend startup, rice balances seed once from supported legacy rice names/classes, summing any old location rows. Unmatched old products are retained in legacy tables and require owner review; they are not guessed into the three rice products. Never reset the database to switch versions.

The new workflow stores balances in rice_products, actions in rice_actions, raw/checked evidence in rice_images, outcomes in rice_requests, movements in rice_history, cases in rice_cases and decisions in rice_decisions. Existing legacy inventory and report APIs remain read-only archive views; old write APIs return HTTP 410. Do not use old clients to change stock after deployment.

Deploy backend and web together using the existing Render/Neon configuration and private environment values. Install MOVIS-0.6.0.apk after the hosted backend supports /v2/state. Its server address remains https://movis-1fxf.onrender.com. Verify owner/staff login, one new image, stock-in/out, full count and separate correction, and a pending return followed by owner decision. Compare both clients' balances and histories.

Use only a disposable database for MOVIS_TEST_DATABASE_URL. Actual PostgreSQL and hosted device outcomes are reported as verified only if their checks were run; see the validation file.

Reports exports include every saved record as CSV or JSON; dashboard lists remain bounded for responsiveness. The SQLite-to-PostgreSQL migration tool now preserves the new workflow tables, evidence and idempotency outcomes as well as legacy records. PostgreSQL verification passed in disposable local schemas; hosted production behavior still needs deployment testing.
