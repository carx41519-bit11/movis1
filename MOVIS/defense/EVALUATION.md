# Verification evidence and research evaluation plan

## Evidence boundary as of 2026-10-03

| Check | Status | Evidence and limit |
|---|---|---|
| Domain/HTTP/WSGI and disposable PostgreSQL suite | Passed | 70 tests; PostgreSQL 18.6 loopback, not production Neon |
| Model storage validation | Passed | 4 tests: demo avoids fetch, HTTPS/checksum requirements, atomic verified bytes, bad checksum; fixture bytes are not YOLO weights |
| Browser simulated responses | Passed | Password validation/errors, refresh/login/logout/expiry, inactivity on reload, no scan input, responsive desktop/390px mobile |
| Real local WSGI browser/API integration | Passed | HttpOnly cookie unreadable by JS, cookie sign-in persists, Android-style bearer additions, exact retries, restock once, count/history, viewer denial, password revocation |
| Android source compilation | Passed | Java 17 language level against Android API; no device/emulator behavior claim |
| Android packaging/signature | Passed with documented build workaround | 0.5.0/versionCode5/API26; APK v2 signature valid, same signer as previous release; device install untested |
| Public hosted /health and website | Passed | 200; mode demo. Unauthorized inventory and empty login returned 401 |
| Updated cloud sign-in/stock/return persistence | Untested | New source not deployed during this audit; private credentials not supplied |
| Actual Android install/camera/EXIF/network | Untested | Requires target phone and updated hosted backend |
| New Docker/YOLO image | Untested | Docker unavailable locally; hosting build/inference still needed |
| Warehouse YOLO/counting accuracy | Blocked | Item classes, trained model and held-out dataset absent |
| User acceptance/usability study | Blocked | Selected warehouse, participant approval and collected responses absent |
| Backup restore drill | Untested | Configure private backup and restore into an isolated database |

Do not add these software test counts to a detection accuracy statistic. Unit tests,
mocked browser responses, actual local HTTP, public hosted reachability and device
tests represent different evidence. A successful build is not a research outcome.

## Repeat software checks

From the extracted project root install Python backend/requirements-cloud.txt in a
virtual environment. Run:
```text
python -m unittest discover -s backend -p "test_*.py"
```
For PostgreSQL tests, set MOVIS_TEST_DATABASE_URL privately to a disposable database
whose account can create/truncate disposable test tables. Never point it to production.
Without that variable PostgreSQL cases are skipped, not passed. The CI workflow
supplies a disposable Postgres service. tests/README.md explains browser checks.

After deployment test both Android and web with actual authorized test accounts:
photo discard, incoming addition, full physical reconciliation, concurrency conflict,
return accepted/damaged/restocked, duplicate retry, session expiry and viewer denial.
Record device model, Android version, build, server commit, database type and mode.

## Dataset and model evaluation

1. Obtain warehouse/photo permission and define counting unit and class labels.
   A carton containing bottles is not automatically equivalent to each bottle.
2. Capture different phones, sessions, shelf backgrounds, lighting, distances and
   overlaps. Include empty shelves/confusing objects. Annotate visible units using
   YOLO bounding boxes, and record complete physical counts separately.
3. Split by capture session/day/shelf BEFORE augmentation so near-duplicate frames
   do not cross train/validation/test. A proposed 70/15/15 split is a starting design,
   subject to adviser approval and class coverage; it is not a collected dataset.
4. Train using training/README.md. Tune model/confidence using validation data only.
   Test the final selected weights once on untouched test data.
5. Report per-class precision, recall and mAP@0.5 and mAP@0.5:0.95 using the model's
   validation output. Include sample counts and failure categories.
6. Count MAE = sum(abs(predicted visible count - annotated visible count))/N.
   Exact-count accuracy = number of exact visible-count matches/N. Report per class
   and condition; measure raw model counting separately from user-corrected totals.
7. Do not compare visible detection counts to hidden physical stock as if they were
   the same ground truth. Reconciliation tests assess the user's verified total.

No detection or counting outcome is supplied. Record results in evaluation-counting.csv.
[Ultralytics training](https://docs.ultralytics.com/modes/train/),
[validation](https://docs.ultralytics.com/modes/val/).

## Performance and acceptance

Measure at least warm and cold hosted requests separately. Record client round-trip
time and server processing_ms; the current processing_ms includes snapshot/inference
and scan persistence, not just neural-network computation. Include median and p95,
sample count, model, image dimensions, hardware, network and mode. Set acceptable
latency and accuracy targets with the adviser before examining results. Do not count
free-server wake-up as warm-model speed or a demo scan as YOLO performance.

Ask intended administrator/operator/viewer users to perform representative tasks:
locate stock, verify/correct a scan, discard, reconcile, process a return and inspect
history. Measure completion, errors, assistance and time. A proposed five-point
questionnaire can assess clarity, ease of correction, trust in histories, task fit and
willingness to use. This custom questionnaire is not presented as a validated SUS
instrument. Record participant role, consent, recruitment, number and open comments;
do not invent a participant population or an acceptance percentage.

Functionality gate: all critical authorization, duplicate handling, adjustment and
return paths pass on the hosted system and actual phone. Research gate: actual
model/dataset/metrics and usability data exist, are honestly reported and meet
pre-agreed criteria. Final manuscript gate: template text removed, chapter numbering
corrected, references verified, ethics and warehouse scope documented.

Readiness remains not ready for a final evaluated defense until these gates close.

