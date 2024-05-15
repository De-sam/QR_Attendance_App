"""This file contains all the models for this  application"""
from sqlalchemy.orm import backref
from sqlalchemy.sql import func
from . import db
from flask_login import UserMixin

# Association table for the many-to-many relationship between Users and Locations
user_locations = db.Table('user_locations',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    """User model for storing user details."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    organizations = db.relationship('Organization', backref=backref('created_by_users', lazy=True), lazy='dynamic', cascade="all, delete-orphan")
    locations = db.relationship('Location', secondary=user_locations, backref=db.backref('members', lazy='dynamic'))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    can_update_timezone = db.Column(db.Boolean, default=False, nullable=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Organization(db.Model):
    """Organization model for storing organization details."""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    locations = db.relationship('Location', backref='organization', lazy=True, cascade="all, delete-orphan")
    created_by = db.relationship('User', backref=backref('created_organizations', lazy=True), lazy=True)

    def __repr__(self):
        return f"Organization('{self.name}', '{self.locations}', '{self.code}')"

class Location(db.Model):
    """Location model for storing physical location details."""
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    alias = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    qr_codes = db.relationship('QRCode', backref='location', lazy=True, cascade="all, delete-orphan")
    deadline = db.Column(db.Time, nullable=True)

    def __repr__(self):
        return f"Location('{self.name}', '{self.address}')"

class QRCode(db.Model):
    """QRCode model for storing QR code data related to a location."""
    __tablename__ = 'qrcodes'

    id = db.Column(db.Integer, primary_key=True)
    qr_data = db.Column(db.Text, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)

    def __repr__(self):
        return f"QRCode('{self.qr_data}')"
    
class JoinRequest(db.Model):
    """JoinRequest model for storing user requests to join organisations"""
    __tablename__ = 'join_requests'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))

    organization = db.relationship('Organization', backref=db.backref('join_requests', lazy=True))
    user = db.relationship('User', backref=db.backref('join_requests', lazy=True))
    location = db.relationship('Location', backref=db.backref('join_requests', lazy=True))

    @property
    def organization_name(self):
        return self.organization.name

    @property
    def user_name(self):
        return self.user.username

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    clock_in_time = db.Column(db.DateTime, nullable=False, default=func.now())
    clock_out_time = db.Column(db.DateTime)
    is_clocked_in = db.Column(db.Boolean, default=True)  # True means user has clocked in
    status = db.Column(db.String(50), default='Absent')

    user = db.relationship('User', backref='attendance_records')
    location = db.relationship('Location', backref='attendance_records')

    def __repr__(self):
        return f"<Attendance {self.user.username} {self.location.name} {self.clock_in_time} {self.is_clocked_in}>"


class UserTimeZone(db.Model):  
    __tablename__ = 'usertimezones'    
   
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    time_zone = db.Column(db.String(50), nullable=False)
    
