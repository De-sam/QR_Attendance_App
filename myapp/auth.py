from flask import Blueprint
from myapp import render_template,request

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=['GET','POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    return render_template('login_signup.html')

@auth.route("/signup", methods=['GET','POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    return render_template('login_signup.html')

 
@auth.route('/forgot_password')
def forgot_password():
    """This is the home route"""
    return "forgot password"

@auth.route('/logout')
def log_out():
    """This is the home route"""
    return "logout"
