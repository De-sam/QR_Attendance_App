from flask import Blueprint,render_template
from flask_login import login_required,current_user

views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')

@views.route("/dashboard")
@login_required
def dashboard():
    return render_template('dashboard_base.html', name=current_user.username)

@views.route("/create_org")
@login_required
def create_org():
    return render_template('create_org.html', name=current_user.username)

@views.route("/manage_org")
@login_required
def manage_org():
    return render_template('manage_org.html', name=current_user.username)

@views.route("/join_org")
@login_required
def join_org():
    return render_template('join_org.html', name=current_user.username)
