from flask import Blueprint
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=['GET','POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
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
            new_user = User(email = email, password = forgot_password )
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
def log_out():
    """This is the home route"""
    return "logout"
