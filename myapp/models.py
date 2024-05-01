"""This file contains all the models for this  application"""
from sqlalchemy.orm import backref
from sqlalchemy.sql import func
from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    """user model"""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    organizations = db.relationship('Organization', backref=backref('creator', lazy=True), lazy='dynamic')

class Organization(db.Model):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False , unique=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    locations = db.relationship('Location', backref='organization', lazy=True)

class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    long = db.Column(db.Float, nullable = False)
    lat = db.Column(db.Float, nullable = False)
    alias = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    