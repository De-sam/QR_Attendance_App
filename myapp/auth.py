from flask import Blueprint, session, render_template, request, flash, redirect, url_for
from . import db, google
from .models import User
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime, timedelta

auth = Blueprint("auth", __name__)

# Google OAuth routes
@auth.route('/login/google')
def login_google():
    return google.authorize(callback=url_for('auth.authorized', _external=True))

@auth.route('/login/callback')
def authorized():
    response = google.authorized_response()
    if response is None or response.get('access_token') is None:
        flash('Access denied: reason={} error={}'.format(
            request.args['error_reason'],
            request.args['error_description']
        ), 'danger')
        return redirect(url_for('auth.login'))

    session['google_token'] = (response['access_token'], '')
    user_info = google.get('userinfo')
    email = user_info.data['email']

    user = User.query.filter_by(email=email).first()
    if not user:
        # Create a new user if not exists
        user = User(email=email, username=email.split('@')[0])
        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    session.permanent = True
    session['last_activity'] = datetime.now()
    return redirect(url_for('views.dashboard'))

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')

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
