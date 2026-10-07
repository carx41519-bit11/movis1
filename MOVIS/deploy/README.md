# Free online setup: PythonAnywhere

The project is prepared for online hosting; it has NOT been deployed yet. No live online URL exists until a hosting account is created and the web app is configured. The local Android/website connection continues to work.

The selected free option is PythonAnywhere's Beginner account. It includes one Python web app, HTTPS, and 512 MiB storage. Its current free-account documentation lists a one-month web-app expiry. Check the Web tab regularly and renew/extend before the displayed expiry. See [pricing](https://www.pythonanywhere.com/pricing/) and [free-account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures).

This setup hosts inventory records and the demo scanner. A warehouse-trained YOLO model is not included. The current PyTorch/Ultralytics implementation may exceed free storage or memory limits; real inference on this plan is unverified. Do not assume it will work without benchmarking and checking dependencies. Inventory management and manual entry do not require YOLO.

## 1. Create the hosting account

Create a free Beginner account on PythonAnywhere. Keep account signup/login and email verification under your control. Do not post hosting passwords in this chat or in GitHub.

## 2. Upload the project

On PythonAnywhere's Files tab, upload the updated project ZIP into your home directory. In a Bash console, unzip it:

```bash
unzip MOVIS-project.zip
```

The resulting folder must be `/home/YOUR_USERNAME/MOVIS` with `backend`, `web`, and `deploy` inside it. Alternatively, clone a GitHub repository containing the project into `~/MOVIS`. Uploading the ZIP does not require linking GitHub or making the repository public.

## 3. Create the Python environment

In a PythonAnywhere Bash console (choose a Python version offered by that account, 3.11 or newer):

```bash
python3.11 -m venv ~/movis-venv
~/movis-venv/bin/pip install -r ~/MOVIS/backend/requirements.txt
```

If Python 3.11 is unavailable, replace it with another offered version and select that same version when configuring the web app. This free setup uses PythonAnywhere's WSGI worker, so Gunicorn is not required.

## 4. Initialize your private cloud account

```bash
~/movis-venv/bin/python ~/MOVIS/backend/initialize_cloud.py --db ~/movis-data/movis.db
```

Choose a private administrator username and a NEW password of at least 12 characters. The public `demo / movis-demo-2026` credentials are deliberately rejected for initial cloud setup. Add `--seed-demo` only if you intentionally want a fictional demo catalog. Without that option, the cloud catalog starts empty.

## 5. Configure the website

On the Web tab:

1. Choose Add a new web app and accept the free `YOUR_USERNAME.pythonanywhere.com` domain.
2. Choose Manual configuration and the same Python version used above.
3. Set the virtualenv path to `/home/YOUR_USERNAME/movis-venv`.
4. Open the WSGI configuration file. Replace its example content with `MOVIS/deploy/pythonanywhere_wsgi.py`.
5. Enable Force HTTPS if the Web tab offers that switch.
6. Reload the web app.

Open `https://YOUR_USERNAME.pythonanywhere.com/health`. It must show `status: ok`. Then open the root URL to sign in to the inventory dashboard using your NEW cloud credentials.

## 6. Connect Android

Enter the actual assigned URL in MOVIS's Server address field:

```text
https://YOUR_USERNAME.pythonanywhere.com
```

Do not add `:8080` to the hosted HTTPS URL. Sign in with your cloud account. Android and the website now use the same online database, and your local computer no longer needs to remain on. Both devices still need internet access.

## 7. Verify before using real inventory

- Sign in on Android and web using the cloud URL.
- Create/register an item and location through Android Manage.
- Edit quantity in Android and refresh the web dashboard to check the saved total.
- Test demo photo Add versus Discard; inference alone must not change stock.
- Test a return's inspection/restock workflow.
- Reload the hosted web app and verify stock remains saved.
- Back up `~/movis-data/movis.db` regularly and monitor disk usage and expiry.

No real YOLO results are claimed. Do not install large PyTorch packages into a 512 MiB account without first checking their sizes and host limits.

## Keep your existing local stock (optional migration)

Before switching operational data, choose whether to start fresh or migrate the current database. To migrate without copying a database while it is being written, use SQLite's online backup API on your computer and save into the workspace's `work` folder:

```python
import sqlite3
source=sqlite3.connect('outputs/MOVIS/backend/demo.db')
backup=sqlite3.connect('work/movis-cloud-backup.db')
source.backup(backup)
backup.close()
source.close()
```

Run that snippet from the project workspace. Download/upload the backup privately via PythonAnywhere's Files tab, rename it `movis.db`, and place it in `~/movis-data` BEFORE the cloud web app starts. Never commit it to GitHub. For an imported demo administrator, immediately replace the known password:

```bash
~/movis-venv/bin/python ~/MOVIS/backend/initialize_cloud.py --db ~/movis-data/movis.db --reset-admin-password demo
```

Changing the username here to an existing administrator lets you reset that administrator's password. Data is preserved; that account's previous sessions are revoked. This project has not copied or uploaded your local database anywhere.

## Paid alternative

`render-paid.yaml` is an optional Render blueprint that creates paid compute plus a disk. It is not selected for this free deployment. Render free web services lose local SQLite files on restart/spin-down and cannot attach a disk; deploying this SQLite backend there for free would risk lost inventory. See [Render free-plan limits](https://render.com/docs/free).
