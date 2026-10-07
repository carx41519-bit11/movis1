# Deployment and trained model installation

## Upload and protect existing data

Use the supplied MOVIS-defense-source.zip. Extract it; do not upload the ZIP itself
as application source. It contains MOVIS-deployable/ with backend, web, android,
models, training, deploy and defense folders, plus root render.yaml and a root
.github/workflows/verify.yml for your current nested GitHub layout.

Upload the extracted MOVIS-deployable contents to the matching GitHub directory,
replacing same-named files. Put render.yaml and .github at repository root. The
UPLOAD-FILES.txt manifest lists every source file included. Source packaging omits
databases, photos, model weights, APKs, keystores, passwords, local.properties and
environment files. Keep a private backup of the database before deployment.

Do not erase or recreate Neon, replace DATABASE_URL, seed a second live database,
or overwrite administrator credentials. Existing password hashes remain valid and
upgrade after successful login. Existing stock/history is preserved.

Two new tables and one index are additive: session_activity, auth_attempts and
auth_attempts_lookup. The existing schema initializer creates them in a locked
transaction at startup for both SQLite and PostgreSQL. There is no column rewrite,
table drop or inventory import. Test on an isolated database/Neon branch first.
No manual SQL pasted into Neon is needed with the current schema-owner credential.
If you restrict the app's DDL permission later, apply the supplied schema additions
with an authorized migration account before deployment. Production was not changed
by this audit.

## Render configuration

Preserve the working settings. For the supplied nested repository blueprint:
- Root Directory: blank.
- Dockerfile Path: MOVIS-deployable/Dockerfile.
- Docker Build Context Directory: MOVIS-deployable.
- Health check: /health.
- DATABASE_URL: existing private Neon PostgreSQL URL.
- MOVIS_MODE: demo until a compatible model is ready.
- MOVIS_HTTPS_HOSTING: 1.
- MOVIS_SEED_DEMO: affects only a fresh empty database; use 0 for a real warehouse.
- Administrator bootstrap variables are needed only for an empty database; an
  existing account is not reset by changing those values.

Commit the upload and deploy the latest commit on Render. Wait for Live. Check
https://movis-1fxf.onrender.com/health, open the website and sign in. The first web
sign-in after upgrade may require reauthentication because browser bearer storage
has been replaced with a cookie. Install the new 0.5.0 APK and test with mobile data
and the computer switched off. Browser and Android must use the same HTTPS URL.

The GitHub workflow runs SQLite/PostgreSQL tests, a demo Docker build and Android
packaging. Its execution in your GitHub account is still unverified; inspect the
Actions result after upload. A workflow kept only inside MOVIS-deployable/.github
would not run: the supplied root .github placement corrects this.

## Choose one trusted model delivery method

Train/evaluate a YOLO detection model on your actual classes first. Only load
trusted weights produced by your own training process; a .pt file is executable
model content, not an ordinary untrusted photograph. Do not upload training images
or database credentials to a public repository.

Embedded model:
1. Place best.pt at MOVIS-deployable/models/best.pt in a controlled/private repo.
2. Git ignores .pt by default; explicitly include your intended file if appropriate.
   Docker permits only models/best.pt via its narrow .dockerignore exception.
3. Select MOVIS-deployable/Dockerfile.yolo on Render; keep the same build context.
4. Set MOVIS_MODE=yolo and MOVIS_WEIGHTS=/app/models/best.pt. Redeploy.
5. Dockerfile.yolo copies models and installs CPU PyTorch and Ultralytics.

Verified private HTTPS download alternative:
1. Store best.pt once in controlled object storage (Neon storage or another service
   is optional; it is not stored in your inventory database).
2. Set MOVIS_WEIGHTS_URL to its private HTTPS download URL in Render's environment.
   Set MOVIS_WEIGHTS_SHA256 to the actual file's SHA256 hex digest. Do not publish
   signed URLs. Obtain the hash in PowerShell: Get-FileHash -Algorithm SHA256 best.pt.
3. Unset MOVIS_WEIGHTS if no embedded file exists, select Dockerfile.yolo and set
   MOVIS_MODE=yolo. The loader downloads into /tmp, checks HTTPS redirects, a
   250 MiB limit and checksum, then atomically installs the file before loading.
4. The temporary filesystem is not persistence: this download repeats on service
   replacement. Expiring URLs must be renewed before future startup.

Either method fails startup for missing/invalid weights instead of faking YOLO.
Catalog model_class must EXACTLY match each model label. Unknown classes remain
visible but cannot silently create inventory. Register each item/location stock
before adding or reconciling. Android needs no model file and no APK rebuild just
to update server weights.

Check inference memory and latency on the actual host. The free Render plan has
512 MB and an ephemeral filesystem; sufficient YOLO memory is not guaranteed.
Do not choose a paid plan or provision resources without reviewing costs.
[Render compute plans](https://render.com/docs/compute-plans),
[free deployment limits](https://render.com/docs/free),
[Ultralytics prediction](https://docs.ultralytics.com/modes/predict/).

## Recovery and maintenance

For a boot failure inspect the first meaningful exception in Render logs. Check
database URL/SSL, bootstrap rules, Docker context and model availability. Do not
solve an error by replacing a live database with an empty one. The ordinary
Dockerfile and MOVIS_MODE=demo provide an explicit demo fallback when deliberately
selected; state that recognition is synthetic. Revert the Git commit and redeploy
for code rollback. The additive tables can remain; do not drop them as rollback.

Record backup schedule, responsible person, retention and a restore drill before
operational use. A provider backup existing is not proof that restoring it works.
Do not print passwords, DATABASE_URL, cookie tokens or private model URLs in logs.
