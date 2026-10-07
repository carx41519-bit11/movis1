> Historical notes from the previous version. Current requirements and verification: PAPER-ALIGNMENT.md and VALIDATION-0.6.0.txt.

# Verification record — 1 October 2026

Latest revision: all 24 backend tests pass; Android Java source compilation passes. Browser verification covers still-photo analysis, changed quantities, exclusion, discard without inventory writes, additive entry, manual stock editing, and mobile width. Real model and Android device validation remain pending.

## Completed

- 19 automated tests passed: 15 domain-service tests and 4 HTTP integration tests, including web dashboard asset serving and path restrictions.
- Stock adjustment tests verified nonnegative integer quantities, required full-count acknowledgement, explicit confirmation, audit differences, exact retry behavior, rejected altered retries, and one commit per scan/item/location.
- Two competing scan adjustments were run concurrently: one committed and the other received a stale-version conflict.
- Return tests verified inspection gates, explicit suitability confirmation, damaged-return rejection, idempotent registration, and a single inventory addition under concurrent restock attempts.
- Permission tests verified viewer restrictions and administrator-only catalog actions.
- HTTP tests verified login, unauthorized access, inventory output, CSV output, logout revocation, invalid-input status, and duplicate-entry conflicts.
- Android Java sources compiled into class files using Java compiler API with Java 17 language targeting against a locally cached Android API archive. This checks source compilation, not Android Gradle packaging or runtime behavior. The compiler API was used to avoid a Windows sandbox archive-close issue in the compiler command-line tool.
- Demo image tests used generated JPEGs and checked that inference does not change inventory. These are software correctness tests, not YOLO accuracy evaluations.
- Web browser checks passed for login/logout, inventory totals, product search, stock filters, return display, empty stock history, shared-backend restock refresh, CSV download, connection error/recovery, and a mobile viewport without page overflow. Desktop/mobile screenshots were visually reviewed. The browser was tested using locally installed Edge in headless mode because the interactive browser tool could not initialize in this session.

## Pending

- Full Android Gradle build with SDK Platform 35 and compatible build tools.
- Installable APK creation and Android emulator/physical-phone testing.
- Camera capture, document picker, image overlay alignment, small-screen layout, and Wi-Fi upload testing on actual devices.
- User acceptance and usability evaluation.
- Real warehouse catalog, annotated images, trained weights, and held-out YOLO evaluation.
- Server hardware benchmarks and end-to-end latency measurements.
- Deployment backup/restore checks; HTTPS and a production server if deployed beyond trusted local testing.

No APK, training accuracy, warehouse evaluation score, or deployed online server is claimed. This package is a tested backend and an Android source prototype ready for Android Studio integration and device verification.
