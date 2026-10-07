"""Copy into the WSGI configuration file on PythonAnywhere's Web tab."""
import os
import sys
from pathlib import Path

# Upload/clone the project into /home/YOUR_USERNAME/MOVIS.
project=Path.home()/'MOVIS'
sys.path.insert(0,str(project/'backend'))
os.environ['MOVIS_DB_PATH']=str(Path.home()/'movis-data'/'movis.db')
os.environ['MOVIS_MODE']='demo'
os.environ['MOVIS_HTTPS_HOSTING']='1'

# Initialize the database with initialize_cloud.py BEFORE reloading this web app.
# Real YOLO hosting requires separately installed inference dependencies and weights.
from webapp import create_app
application=create_app()
