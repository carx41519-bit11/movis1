# MOVIS 0.6.0

Inventory for Elder Jay rice mill: Sinandomeng, Jasmine rice and Buko Pandan rice, each in 25 kg sacks. One sack is one unit. The administrator website and staff Android app share the backend and product balances.

This is the maintained source folder. Neighboring deployment and defense packages are previous versions. Read PAPER-ALIGNMENT.md for requirements, changes, verification, migration and remaining field testing.

## Setup

Install backend/requirements-cloud.txt in your development Python environment. Create a private owner account with `python backend/server.py --db movis.db --init`. Start with `python backend/server.py --db movis.db --host 127.0.0.1 --port 8080 --mode demo`. Open http://127.0.0.1:8080 as administrator. Staff use Android.

The APK uses https://movis-1fxf.onrender.com. Deploy the updated backend and web before using 0.6.0 against that address. This update has not been published to the live service. No production database was changed during development.

Existing accounts and legacy tables are preserved. Supported rice balances migrate once by exact rice name or class. Review any unmatched legacy catalog records before adopting the new balances. New workflows use rice_products; old stock endpoints are disabled to prevent bypassing verification and owner approval.

The scanner is synthetic in demo mode. No trained rice model or measured accuracy is supplied. See training/README.md to connect future trained YOLO26 weights.

## Workflow

Choose stock-in, stock-out, Inventory Count, return or damage before capture. Take new images inside the app using the rear camera at 1x. Review every retained image, correct rice quantities, delete unwanted images and add more. Every sack must be counted once. Saving scans leaves stock unchanged.

Submit transaction posts a movement atomically. Finish count stores the comparison only; an account with adjustment permission must separately confirm a complete-count correction. Changed stock versions require rechecking. Returns and damage await owner inspection and decisions on the website.

Run `python -m unittest discover -s backend -p "test_*.py"`. PostgreSQL tests require MOVIS_TEST_DATABASE_URL pointing only to a disposable database. Build Android with `android/gradlew assembleDebug` or Android Studio. The supplied APK is debug signed for testing. Actual phone capture and hosted integration need device testing.
