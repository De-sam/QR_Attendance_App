from flask import Blueprint
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User
from flask_login import login_user,logout_user,login_required,current_user
from werkzeug.security import generate_password_hash, check_password_hash

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first() 
        if user:
            if check_password_hash(user.password, password):
                flash('logged in sucessfully!!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('password is incorrect', category='error')
        else:
            flash('Email does not exist', category='error')        
            
    return render_template('login_signup.html')
    

@auth.route("/signup", methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('email is already in use.', category='error')
        elif password != confirm_password:
            flash('Your password and your confirm password are not the same!', category='error')
        elif len(password) < 6:
            flash('your password is too short, it must have 6 chracters or more!')
        elif len(email) < 4:
            flash('invalid email address! Please use a valid email.', category='error')
        else:
            new_user = User(email = email, password = generate_password_hash(password, method='pbkdf2:sha256'))
            db.session.add(new_user)
            db.session.commit()
            flash('User created! Signup was sucessful', category='success')
            return redirect(url_for('views.home'))
            
    return render_template('login_signup.html')

 
@auth.route('/forgot_password')
def forgot_password():
    """This is the home route"""
    return "forgot password"

@auth.route('/logout')
@login_required
def log_out():
    """This is my logout route"""
    logout_user()
    return redirect(url_for('auth.login'))
