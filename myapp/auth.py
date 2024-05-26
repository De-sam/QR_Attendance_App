from flask import Blueprint, session, render_template, request, flash, redirect, url_for
from . import db
from .models import User
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import re
from google.oauth2 import id_token
from google.auth.transport import requests
import psycopg2 
from datetime import datetime, timedelta
from flask_oauthlib.client import OAuth
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import os

auth = Blueprint("auth", __name__)

# Initialize OAuth
oauth = OAuth()
oauth.init_app(auth)

# Configure Google OAuth
google_client_id = os.getenv('GOOGLE_CLIENT_ID')
google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

if not google_client_id or not google_client_secret:
    raise ValueError("No Google OAuth credentials set for Flask application")

google = oauth.remote_app(
    'google',
    consumer_key=google_client_id,
    consumer_secret=google_client_secret,
    request_token_params={'scope': 'email profile'},
    base_url='https://www.googleapis.com/oauth2/v1/',
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('user_input')
        password = request.form.get('password')
        user = None

        # Try to find the user by username or email
        if '@' in user_input:
            user = User.query.filter_by(email=user_input).first()
        else:
            user = User.query.filter_by(username=user_input).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            session.permanent = True
            session['last_activity'] = datetime.now()
            return redirect(url_for('views.dashboard'))
        else:
            flash('Login details are incorrect. Please try again.', category='danger')

    return render_template('login_signup.html')

@auth.route("/signup", methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check if email or username already exists in the database
        username_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()

        # Validation checks
        if email_exists:
            flash('Email is already in use.', category='danger')
        elif username_exists:
            flash('Username already taken, choose another.', category='danger')
        elif password != confirm_password:
            flash('Your password and your confirmation password do not match!', category='warning')
        elif len(password) < 6:
            flash('Your password is too short, it must have 6 characters or more!', category='warning')
        elif not re.search("[A-Z]", password):
            flash('Your password must include at least one uppercase letter.', category='warning')
        elif not re.search("[0-9]", password):
            flash('Your password must include at least one number.', category='warning')
        elif not re.search("[!@#$%^&*(),.?\":{}|<>]", password):
            flash('Your password must include at least one special character.', category='warning')
        elif len(email) < 4:
            flash('Invalid email address! Please use a valid email.', category='danger')
        else:
            # Password is valid and checks have passed
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Signup was successful! Please login', category='success')
    return render_template('login_signup.html')

@auth.route('/forgot_password')
def forgot_password_modal():
    """This is the home route"""
    return render_template('forgot-password-modal.html')

@auth.route('/logout')
@login_required
def log_out():
    """This is my logout route"""
    logout_user()
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/login/google')
def login_google():
    callback_url = url_for('auth.callback_google', _external=True)
    return google.authorize(callback=callback_url)

@auth.route('/callback/google')
@google.authorized_handler
def callback_google(resp):
    if resp is None:
        flash('You denied the request to sign in.')
        return redirect(url_for('auth.login'))

    access_token = resp['access_token']
    google_id = resp['id_token']['sub']

    # Extract user information from the ID token
    user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').data
    username = user_info.get('name')
    email = user_info.get('email')

    # Check if the user exists in the database
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        # Create a new user if they don't exist
        user = User(
            username=username,
            email=email,
            google_id=google_id
        )
        db.session.add(user)
        db.session.commit()

    # Log the user in
    login_user(user, remember=True)

    return redirect(url_for('views.dashboard'))