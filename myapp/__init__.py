import os
from os import path
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_session import Session
from dotenv import load_dotenv
from datetime import datetime
from authlib.integrations.flask_client import OAuth
import pytz
import psycopg2

load_dotenv()
db = SQLAlchemy()
oauth = OAuth()

def create_app():
    app = Flask(__name__)
    
    # Load configuration from environment variables
    secret_key = os.getenv('SECRET_KEY')
    database_url = os.getenv('DATABASE_URL')
    
    if not secret_key or not database_url:
        raise ValueError("No SECRET_KEY or DATABASE_URL set for Flask application")
    
    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    app.config['SESSION_TYPE'] = 'filesystem'  # Use filesystem for session storage
    app.config['TIMEZONE'] = 'Africa/Lagos'
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    Session(app)  # Initialize the Flask-Session extension
    
    # Initialize OAuth
    oauth.init_app(app)
    oauth.register(
        'google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        client_kwargs={'scope': 'openid profile email'},
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    )
    
    # Register blueprints
    from .views import views
    from .auth import auth
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    
    # Create database
    create_database(app)
    
    # Configure login manager
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    return app

def create_database(app):
    if not path.exists('myapp'):
        with app.app_context():
            db.create_all()
            print('Created database!')

