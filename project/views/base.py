from project import app
from project.views import admin

app.register_blueprint(admin.bp, url_prefix='/admin')
