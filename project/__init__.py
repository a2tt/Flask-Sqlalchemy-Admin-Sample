from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object('settings')

db = SQLAlchemy(app)

from project.views import base as base_view
from project.models import base as base_models


@app.route('/')
def index():
    return 'Index Page'
