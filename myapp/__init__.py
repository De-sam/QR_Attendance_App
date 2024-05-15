import os
from os import path
from flask import Flask,render_template,request,redirect,url_for,flash
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import psycopg2 
import pytz
from datetime import datetime 


load_dotenv()
db = SQLAlchemy()

print("SECRET_KEY:", os.getenv('SECRET_KEY'))
print("DATABASE_URL:", os.getenv('DATABASE_URL'))

def create_app():
    app = Flask(__name__)
    secret_key = os.getenv('SECRET_KEY')
    database_url = os.getenv('DATABASE_URL')
    
    if not secret_key or not database_url:
        raise ValueError("No SECRET_KEY or DATABASE_URL set for Flask application")
    
    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

# Set the timezone for the Flask application
    app.config['TIMEZONE'] = 'UTC'

    
    db.init_app(app)
    migrate = Migrate(app, db)
   
    
   
    



    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

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
        

