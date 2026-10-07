# Reproducible verification for MOVIS 0.6.0

Install backend/requirements-cloud.txt, then run `python -m unittest discover -s backend -p "test_*.py"` from the project root. New workflows are in test_rice.py and inherited PostgreSQL cases in test_rice_postgres.py. Set MOVIS_TEST_DATABASE_URL only to a disposable database; test schemas are removed afterward.

For browser integration, install Playwright in your development environment. Run `python tests/browser_server.py`, then `node tests/browser_integration.cjs` from the project root. The server creates disposable test data in .work and synthetic images. On Windows an installed Edge is used. Stop the server afterward. These checks use synthetic detections and do not test the physical Android camera.

Compile/install Android from android/ with Android Studio or Gradle. Test a real phone against a test backend before production use. See PAPER-ALIGNMENT.md and VALIDATION-0.6.0.txt for completed checks and remaining field testing.
