"""This file contains all the models for this  application"""

from sqlalchemy.sql import func
from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    """user model"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())  