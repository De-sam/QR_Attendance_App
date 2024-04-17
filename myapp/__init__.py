from os import path
from flask import Flask,render_template,request,redirect,url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'helloworld'

    
    return app

