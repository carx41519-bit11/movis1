# Prioritized audit and corrections

Audit date: 2026-10-03. Canonical source: outputs/MOVIS. Existing inventory and
production credentials were not changed. Corrections are local pending deployment.

| Priority | Evidence and problem | Effect | Correction and verification |
|---|---|---|---|
| P0 remaining | Hosted /health reports demo; no warehouse weights supplied | Cannot claim actual YOLO recognition/accuracy | Demo remains explicit. Model delivery integration completed locally; actual inference/evaluation blocked on trusted weights |
| P1 fixed | Android only submitted /scan-additions despite backend /adjustments | Document's verified count comparison missing from the UI | Complete count screen, physical-count checkbox, previous/new/difference review; Java compilation and APK packaging; backend API tests |
| P1 fixed | adjust did not check scan_commits | A photo used for incoming stock could be reused to reconcile another item | Reject reconciliation after incoming commit; SQLite and PostgreSQL regression check |
| P1 fixed | Browser saved bearer token in sessionStorage | JavaScript could read the credential after an XSS flaw | HttpOnly SameSite cookie for web; token never returned in web-login JSON; Android bearer path preserved; real browser/API integration |
| P1 fixed | Only browser inactivity lock and process-memory request limits | Tokens survived long API inactivity; restart/multiple workers bypassed limiter | Database-backed attempt windows and session_activity; 30-minute API idle and eight-hour absolute expiry; restart/idle tests on both databases |
| P1 fixed | Password hash used 200000 PBKDF2 rounds; changing algorithms would invalidate old hashes | Weaker password protection and migration risk | New PBKDF2 SHA256 600000 format; legacy verification and upgrade on successful login; account IDs retained; SQLite/PostgreSQL tests |
| P1 fixed | User creation trimmed password whitespace | A entered password could differ from stored one | Preserve password exactly; enforce new-account 12–128 characters; whitespace tests |
| P1 fixed | Image parsing omitted TypeError/OSError | Invalid or truncated uploads could return 500 | Reject malformed images with domain error; size and pixel limits remain; regression tests |
| P1 fixed | Unbounded integers could exceed PostgreSQL INTEGER | Failed writes/overflow and inaccurate Android total | Enforce signed 32-bit quantity maximum and bounds on resulting balances; Android aggregate uses long; overflow tests |
| P1 fixed | YOLO Dockerfile installed dependencies but did not copy a model | Deployment fails or stays in demo | Explicit models directory/copy, narrow Docker ignore exception, optional checksum-verified HTTPS download; storage contract tests |
| P2 fixed | Local and WSGI routes diverged | Local verification did not reflect deployment security | Local server delegates to the same WSGI application; real HTTP regression tests |
| P2 fixed | Android bitmap decoded without applying EXIF orientation | Rotated photos could reach inference and show incorrect orientation | Apply native EXIF transformation before JPEG upload; compile verified; phone orientation check still required |
| P2 fixed | Android 401 remained on old screen; timeout messages lacked uncertain-write guidance | Confusing expired sessions and unsafe retries | Return to sign-in on 401; explicit server wake-up and uncertain-write guidance; stable request keys retained |
| P2 fixed | Website lacked scan verification report after scanner removal | Weak traceability of the Android workflow during defense | Read-only scan history and CSV on Stock activity; no capture/upload UI; browser/API verification |
| P2 fixed | History screens remained in hidden DOM on logout | Sensitive records lingered in the signed-out view | Clear in-memory state and rendered records on sign-out; browser checks |
| P2 fixed | Several guides still described local-only hosting or browser scans | Contradictory defense/deployment statements | Current guides rewritten; remaining historical notes identified as superseded |

## Remaining limits and boundaries

- No operational warehouse catalog, trained model, held-out detection/counting
  results, user study, real-device measurements or hosted authenticated test is supplied.
- Docker images could not be built locally because Docker is unavailable. Render
  built the earlier demo image; the new YOLO image and checksum download deployment
  still need a staging deploy. CPU PyTorch may exceed free hosting memory.
- Reports currently return full histories. For larger warehouses add pagination
  and server filters before scaling; these were not invented as completed work.
- Transactions use one shared write lock for simple correctness. This suits a
  small warehouse but serializes writes, including authentication activity updates.
- Attempt limits are account-based plus a shared global ceiling. Avoiding trusted-IP
  assumptions prevents forwarded-header bypass, but a global attack can temporarily
  delay legitimate logins. Edge/WAF limits and MFA are future improvements.
- Database credentials can change audit rows; stock history is traceable, not
  cryptographically tamper-proof. Restrict administrator/database access and back up.
- No offline synchronization or reliable count of unseen objects is implemented.
- Debug APK is signed for direct capstone testing, not a Play Store release.
- Existing legacy sessions receive activity tracking when first used after upgrade;
  they retain their original absolute expiry. New logins have both expiry controls.

Security references verified during this audit:
[OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

