import os

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__, static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////%s/urls.db' % os.getcwd()
app.config['UPLOAD_FOLDER'] = '%s/uploads/' % os.getcwd()

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

import shrls.views
from shrls.models import DBSession

@app.teardown_appcontext
def shutdown_session(exception=None):
    DBSession.remove()
