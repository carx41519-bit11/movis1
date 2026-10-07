> Earlier setup notes. Current instructions: defense/DEPLOYMENT.md and defense/USER-GUIDE.md (0.5.0).

# Deploy MOVIS without keeping your computer on

This release adds PostgreSQL support and a Render Docker Blueprint. Android and
web use the same Python API and the same database. No service has been deployed
into your accounts by preparing these files.

## 1. Choose whether to keep your current data

For a fresh DEMO cloud project, use the Blueprint as supplied: MOVIS_MODE=demo and
MOVIS_SEED_DEMO=1. A new administrator is created only for an empty database.
For a fresh actual warehouse catalog, set MOVIS_SEED_DEMO=0 before deploying.

To preserve existing SQLite data, migrate BEFORE the first hosted startup:
- Make a private backup and stop the local server while preparing migration.
- Create an empty Neon database.
- Install backend/requirements-cloud.txt using Python.
- Set DATABASE_URL privately in your local environment (never paste it into GitHub).
- From backend, run: python migrate_sqlite_to_postgres.py --source demo.db
- The importer uses a consistent SQLite snapshot and one destination transaction.
  It refuses a nonempty target, preserves IDs/history/password hashes, resets ID
  sequences, and does not copy sessions. Users sign in again using their existing
  credentials. It leaves the original SQLite database intact.
- Set MOVIS_SEED_DEMO=0 and deploy. Back up the cloud database before future migrations.

## 2. Create a Neon PostgreSQL database

Create a Neon account/project. Copy its PostgreSQL connection URL from Connect.
Keep SSL enabled (sslmode=require or verify-full). Prefer the direct connection
URL for this small one-worker service. The driver also disables prepared
statements for compatibility with transaction pooling.

DATABASE_URL is a SECRET. It belongs in Render's environment settings, not in
Android, browser JavaScript, a public repository, screenshots or this guide.

## 3. Upload source to your GitHub repository

Upload the CONTENTS of the clean MOVIS-deployable.zip as the repository root.
The root must contain Dockerfile, render.yaml, backend/, web/ and android/.
Do not upload demo.db, APKs, keystores, keystore.properties, .env, local.properties,
Android build output, virtual environments or cache directories.

The supplied GitHub Actions workflow checks SQLite and a real PostgreSQL service,
builds the Docker image, and builds an Android DEBUG APK. Wait for green checks
before relying on an online deployment. Actions have not been run in your account.

## 4. Deploy on Render

Create a Render account and link your repository. Choose New > Blueprint and
select the repository containing render.yaml. Review the plan before creating.
The supplied Blueprint selects a FREE web service and creates no paid database.

Enter these private values when prompted:
- DATABASE_URL: your Neon PostgreSQL connection URL
- MOVIS_ADMIN_USERNAME: your chosen username for a fresh database
- MOVIS_ADMIN_PASSWORD: a NEW private password of at least 12 characters

The Docker build installs Pillow, Gunicorn and psycopg. It launches one worker
with four threads on Render's PORT. The website is served by that same app;
do not deploy this as a static website only. Never use Python's http.server here.

After deployment, Render gives the service its actual HTTPS address. Open that
address plus /health; expect {"status":"ok","mode":"demo"}. Open the root address
for the dashboard, sign in, and test a change. After a successful bootstrap you
may remove MOVIS_ADMIN_PASSWORD from hosting settings; preserve account access.
Existing database accounts are never replaced on a redeploy.

Free Render services sleep after inactivity and have temporary filesystems.
Neon holds inventory independently of that filesystem. Wake-up may be slow;
client timeouts allow longer waits. Free plans have usage limits and are not an
always-on guarantee. For dependable daily warehouse use, budget for paid compute,
database resources/backups, and enough memory for the selected YOLO model.

## 5. Build and install Android 0.3.0

Open android/ in Android Studio and sync. Existing project Gradle/AGP versions
have been preserved. Build a DEBUG APK for initial phone testing.

For a distributable release APK, use Android Studio's Generate Signed Bundle/APK
wizard, create or choose YOUR stable signing key, and build Release. Keep that
key/password private and backed up; use the same key for future updates.
Optional keystore.properties (ignored by Git) supports Gradle signing:
  storeFile=path/to/private-key.jks
  storePassword=YOUR_PRIVATE_PASSWORD
  keyAlias=YOUR_ALIAS
  keyPassword=YOUR_PRIVATE_PASSWORD
Paths are resolved relative to android/. Never commit this file or key.
Without signing configuration an assembleRelease result may be unsigned and is
not an installable release. Verify signing before distributing.

A release APK requires HTTPS. A DEBUG build allows HTTP for local testing only.
If an installed older APK uses a different signing key, Android will reject an
update. Keep the existing key or decide whether to remove the old installation;
removal clears its local settings. Do not repeatedly change release signing keys.

Enter Render's ACTUAL HTTPS root address in Android's Server address field.
Sign in using the same cloud account as the website. You no longer need your
computer, CMD, local Wi-Fi IP, or port 8080. Phone and browser need internet.

The previously supplied APK is 0.2.0 and is not rebuilt by changing source files.
Build and install 0.3.0 to get the Android changes in this release.

## 6. Verify the hosted system

- /health returns JSON; website login succeeds and survives refresh.
- Phone login succeeds over mobile data as well as Wi-Fi.
- Android changes a test quantity; website Refresh shows it.
- Website quantity edit appears when Android reloads Inventory.
- Scanning alone changes no stock; Discard changes no stock.
- Confirmed photo additions increase stock once, including repeated submissions.
- Pending/damaged returns do not increase available stock.
- Accepted returns increase stock only after explicit restock confirmation, once.
- Stock activity, adjustments and return history reflect the changes.
- A Render restart/redeploy retains accounts and inventory in Neon.
- Viewer accounts cannot alter inventory or manage the catalog.
- Log out/expired sessions require sign-in again.

## 7. Enable actual YOLO later

DEMO scans use synthetic detections; photos are not recognized in this mode.
No trained weights or accuracy results are supplied.
Train and evaluate your actual item classes using training/README.md. On suitably
sized inference hosting, install Ultralytics, supply your private tested weights
file, set MOVIS_MODE=yolo and MOVIS_WEIGHTS to its path, and redeploy.
A simple Linux CPU image additionally needs the OpenCV shared libraries; use
Dockerfile.yolo and supply the weights through your host's secure file/storage
mechanism at the configured path. This is an optional deployment variant, not
used by the free demo Blueprint. Test memory usage, processing time and model
licensing before choosing capacity. Do not assume the free service can run YOLO.

## Backups and maintenance

Use PostgreSQL tools/provider backups and test restoring into another database.
A pg_dump backup includes private account hashes and inventory history: protect it.
Keep an independent backup before migrations. Keep secrets in hosting settings.
The login limiter is process-local; this configuration deliberately uses one
worker. Before scaling workers/replicas, add a shared rate limiter and retest.
Offline Android storage/synchronization is not implemented.

References:
https://render.com/docs/blueprint-spec
https://render.com/docs/free
https://neon.com/docs/connect/connect-from-any-app
https://developer.android.com/studio/publish/app-signing
