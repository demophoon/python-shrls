import os

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////%s/urls.db' % os.getcwd()

import shrls.views
from shrls.models import DBSession

@app.teardown_appcontext
def shutdown_session(exception=None):
    DBSession.remove()
