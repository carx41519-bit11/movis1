> Historical notes from the previous version. Current requirements and verification: PAPER-ALIGNMENT.md and VALIDATION-0.6.0.txt.

> Earlier setup notes. Current instructions: defense/DEPLOYMENT.md and defense/USER-GUIDE.md (0.5.0).

# Android UI update — version 0.2.0

The Android source now has a consistent teal-and-navy appearance matching the web monitor.

- Compact MOVIS header and bottom navigation for Inventory, Photo, Returns, and Reports.
- Account menu with Refresh inventory, administrator setup, and Sign out.
- Scrollable sign-in form with permanent field labels, remembered username/server, password visibility, inline validation, and collapsible connection help.
- Inventory summary cards and spaced item cards with locations, available quantities, and Edit quantity.
- Side-by-side capture/picker actions, photo preview, and editable item cards for optional photo stock entry.
- Return registration and readable return cards with clear inspection/restock controls.
- Human-readable report entries instead of raw JSON, while retaining CSV sharing.
- Grouped administrator fields for products, locations, stock registration, and accounts.
- Loading indicators, disabled action buttons during requests, press feedback, and visible errors inside the manual-edit dialog.
- System-bar/cutout and keyboard inset handling, plus scrollable content for smaller displays.

Inventory behavior, account credentials, and backend endpoints are unchanged. Recognition still runs only on a submitted photograph. Existing saved server addresses are preserved; no changing Wi-Fi address is hardcoded.

## Install this update

If Android Studio has this project's `android` folder open, select your phone and press Run to rebuild/install. If working from a separate extracted copy, open the updated `android` folder from the project ZIP instead. Use the same application ID and signing key to update without clearing app settings. Avoid uninstalling just to refresh the UI.

The package version is 0.2.0 (version code 2). Your operational data stays in the backend database. The source archive excludes databases, build caches, local SDK configuration, and stale APKs.

## Verification and limits

Both Android Java sources passed a Java 17-targeted compilation check. A complete Gradle APK build could not run in this session because the wrapper tried to use a restricted cache directory. No new APK or visual phone/emulator verification is claimed. Check login, keyboard visibility, bottom navigation, photo verification, manual edits, and reports on the actual phone after rebuilding.

Android 15 requires apps targeting SDK 35 to handle edge-to-edge insets; see the [official Android inset guidance](https://developer.android.com/develop/ui/views/layout/insets).
