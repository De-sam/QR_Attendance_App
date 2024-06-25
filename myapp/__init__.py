import os
from os import path
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import pytz
from datetime import datetime, timedelta
from .celery import make_celery

load_dotenv()
db = SQLAlchemy()

print("SECRET_KEY:", os.getenv('SECRET_KEY'))
print("DATABASE_URL:", os.getenv('DATABASE_URL'))

def create_app():
    app = Flask(__name__)
    secret_key = os.getenv('SECRET_KEY')
    database_url = os.getenv('DATABASE_URL')
    celery_broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    celery_result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

    if not secret_key or not database_url:
        raise ValueError("No SECRET_KEY or DATABASE_URL set for Flask application")

    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
    app.config['Last_activity'] = datetime.now()
    app.config['TIMEZONE'] = 'Africa/Lagos'

    # Add Celery configuration to app.config
    app.config['CELERY_BROKER_URL'] = celery_broker_url
    app.config['CELERY_RESULT_BACKEND'] = celery_result_backend

    db.init_app(app)
    migrate = Migrate(app, db)

    # Initialize Celery
    celery = make_celery(app)

    from .views import views
    from .auth import auth
    from .dashboard import dash
    from .organisation import org
    from .location import loc
    from .attendance import attend

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(dash, url_prefix='/')
    app.register_blueprint(org, url_prefix='/')
    app.register_blueprint(loc, url_prefix='/')
    app.register_blueprint(attend, url_prefix='/')


    from .models import User, Organization, Location, QRCode, JoinRequest

    create_database(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)    

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app

def create_database(app):
    if not path.exists("myapp/"):
        with app.app_context():
            db.create_all()
            print('Created database!')
