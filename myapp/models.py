"""This file contains all the models for this  application"""
from sqlalchemy.orm import backref
from sqlalchemy.sql import func
from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    """User model for storing user details."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    organizations = db.relationship('Organization', backref=backref('creator', lazy=True), lazy='dynamic', cascade="all, delete-orphan")


class Organization(db.Model):
    """Organization model for storing organization details."""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False , unique=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    locations = db.relationship('Location', backref='organization', lazy=True, cascade="all, delete-orphan")

class Location(db.Model):
    """Location model for storing physical location details."""
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    longitude = db.Column(db.Float, nullable = False)
    latitude = db.Column(db.Float, nullable = False)
    alias = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    qrcode = db.relationship('QRCode', backref='location', uselist=False, cascade="all, delete-orphan")

class QRCode(db.Model):
    """QRCode model for storing QR code data related to a location."""
    __tablename__ = 'qrcodes'

    id = db.Column(db.Integer, primary_key=True)
    qr_data = db.Column(db.Text, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    