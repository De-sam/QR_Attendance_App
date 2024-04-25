from flask import Blueprint,render_template
from flask_login import login_required,current_user

views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
@login_required
def home():
    return render_template('dashboard_base.html', name=current_user.username )

@views.route("/org")
def org():
    return render_template('org.html')