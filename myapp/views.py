from flask import Blueprint,render_template
from flask_login import login_required,current_user
import uuid
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User,Organization,Location



views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')



@views.route("/dashboard")
@login_required
def dashboard():
    organization_count = Organization.query.count()  # Count all organizations
    organizations = Organization.query.all()    
    return render_template(
        'dashboard_base.html', 
        name=current_user.username,
        organization_count=organization_count,
        organizations=organizations
        )

@views.route("/create_org", methods=['GET', 'POST'])
@login_required
def create_org():
    if request.method == 'POST':
        name = request.form.get('name').strip()  # Strip whitespace for consistent comparison
        user_id = 1  # Static for demonstration; use authenticated user's ID in production

        # Check if the organization name already exists
        existing_organization = Organization.query.filter_by(name=name).first()
        if existing_organization:
            flash('An organization with this name already exists.', category='danger')
            return redirect(url_for('views.create_org'))

        if len(name) < 3:
            flash('Organization name must be at least 3 characters long.', category='danger')
            return redirect(url_for('views.create_org'))

        if not name:
            flash('Organization name is required.', category='danger')
            return redirect(url_for('create_organization'))

        code = generate_organization_code(name)
        new_org = Organization(name=name, code=code, user_id=user_id)
        db.session.add(new_org)
        db.session.commit()
        flash('Organization created successfully!', category='success')
        return redirect(url_for('views.manage_org'))
    return render_template('create_org.html', name=current_user.username)

def generate_organization_code(name):
    if len(name) < 3:
        raise ValueError("Name must be at least two characters long")

    # Extract the first, second, and last characters of the name
    first = name[0].upper()
    second = name[1].upper()
    last = name[-1].upper()

    # Generate a UUID, take the first 4 characters
    unique_part = str(uuid.uuid4())[:4]

    # Concatenate and ensure the specific parts are uppercase
    return f"{first}{second}{last}{unique_part}"

@views.route("/manage_org")
@login_required
def manage_org():

    organizations = Organization.query.all()
    return render_template(
        'manage_org.html',
          organizations=organizations,
          name=current_user.username
          )



@views.route("/join_org")
@login_required
def join_org():
    return render_template('join_org.html', name=current_user.username)


@views.route('/add_location/<int:org_id>')
def add_location(org_id):
    # Implementation
    return render_template(
        'add_location.html',
          org_id=org_id,
          name=current_user.username
          )

@views.route('/manage_location/<int:org_id>')
@login_required
def manage_locations(org_id):
    organization = Organization.query.get_or_404(org_id)
    locations = Location.query.filter_by(organization_id=org_id).all()
    return render_template(
        'manage_locations.html',
          organization=organization,
            locations=locations,
            name=current_user.username
            )

@views.route('/delete_organization/<int:org_id>', methods=['POST', 'GET' ])
def delete_organization(org_id):
    organization = Organization.query.get_or_404(org_id)
    locations = Location.query.filter_by(organization_id=org_id).all()

    for location in locations:
        db.session.delete(location)

    db.session.delete(organization)
    db.session.commit()
    flash('Organization and all associated locations deleted successfully!', category='success')
    return redirect(url_for('views.manage_org')) 
