from flask import Blueprint,render_template,session,send_file,Response
from flask_login import login_required,current_user
import uuid
from flask import current_app
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User,Organization,Location,QRCode,JoinRequest,Attendance
import qrcode
from io import BytesIO
import base64
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from haversine import haversine, Unit
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone,date
import pytz





views = Blueprint("views", __name__)

@views.before_request
def before_request():
    session.modified = True
    permanent_session_lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']
    if 'last_activity' in session:
        now = datetime.now(timezone.utc)
        last_activity = session['last_activity']
        session['last_activity'] = now
        if now - last_activity > permanent_session_lifetime:
            flash('Session timed out due to inactivity.', 'warning')
            return redirect(url_for('auth.logout'))
    else:
        session['last_activity'] = datetime.now(timezone.utc)


@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')

@views.route('/admin_only/')
@login_required
def admin_only_function():
    if not current_user.is_admin:
        flash('Unauthorized operation. Admin rights required.', 'danger')
        return redirect(url_for('views.dashboard'))

    # Proceed with admin-only functionality
    ...

