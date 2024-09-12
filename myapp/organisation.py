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

org = Blueprint("org", __name__)




@org.route("/create_org", methods=['GET', 'POST'])
@login_required
def create_org():
    if request.method == 'POST':
        name = request.form.get('name').strip().upper()  # Strip whitespace for consistent comparison
        user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
        
    
        # Check if the organization name already exists
        existing_organization = Organization.query.filter_by(name=name).first()
        if existing_organization:
            flash('An organization with this name already exists.', category='danger')
            return redirect(url_for('org.create_org'))

        if len(name) < 3:
            flash('Organization name must be at least 3 characters long.', category='danger')
            return redirect(url_for('org.create_org'))

        if not name:
            flash('Organization name is required.', category='danger')
            return redirect(url_for('org.create_organization'))

        if not current_user.is_admin:
            current_user.is_admin = True
            flash('You have been granted admin rights.', category='info')
        

        code = generate_organization_code(name)
        new_org = Organization(name=name, code=code, user_id=user_id)
        db.session.add(new_org)
        db.session.commit()
        flash('Organization created successfully!', category='success')
        return redirect(url_for('org.manage_org'))
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
        
    return render_template('create_org.html',
                            name=current_user.username,
                            is_admin=is_admin,
                            is_member=user_locations)

def generate_organization_code(name):
    if len(name) < 3:
        raise ValueError("Name must be at least three characters long")

    # Extract the first, second, and last characters of the name
    first = name[0].upper()
    second = name[1].upper()
    last = name[-1].upper()

    # Generate a UUID, take the first 4 characters
    unique_part = str(uuid.uuid4())[:4]

    # Concatenate and ensure the specific parts are uppercase
    return f"{first}{second}{last}{unique_part}"

@org.route("/manage_org")
@login_required
def manage_org():

    organizations = Organization.query.filter_by(user_id=current_user.id).all()
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations

    return render_template(
        'manage_org.html',
          organizations=organizations,
          name=current_user.username,
          is_admin=is_admin,
          is_member=user_locations
          )


@org.route("/join_org", methods=['GET', 'POST'])
@login_required
def join_org():
    if request.method == 'POST':
        code = request.form.get('code')
        organization = Organization.query.filter_by(code=code).first()
        if organization:
            locations = Location.query.filter_by(organization_id=organization.id).all()
            user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
            is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
            user_locations = current_user.locations
            return render_template('join_org.html', 
                                    organization=organization,
                                    locations=locations,
                                    is_admin= is_admin,
                                    is_member = user_locations)
        else:
            flash('No organization found with the provided code..', category='warning')
            return redirect(url_for('org.join_org'))
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template('join_org.html',
                            name=current_user.username,
                            is_admin= is_admin,
                            is_member = user_locations)

@org.route('/join_request/<int:organization_id>', methods=['GET', 'POST'])
@login_required
def join_request(organization_id):
    organization = Organization.query.get_or_404(organization_id)
    user = current_user

    if request.method == 'POST':
        location_ids = request.form.getlist('location_ids')  # Retrieve list of location IDs from the form

        for location_id in location_ids:
            # Check if a request to join each location has already been made
            existing_request = JoinRequest.query.filter_by(location_id=location_id, user_id=user.id).first()
            if existing_request:
                location = Location.query.get(location_id)
                flash(f'You have already requested to join {organization.name} at {location.alias}.', 'warning')
                continue  # Skip this location and continue with others

            # Create a new join request for each location
            join_request = JoinRequest(organization_id=organization_id, user_id=user.id, location_id=location_id)
            db.session.add(join_request)

        db.session.commit()
        flash(f'Your requests to join selected locations have been sent successfully!', category='success')
        return redirect(url_for('dash.dashboard'))

    return redirect(url_for('dash   .dashboard'))

@org.route('/approve_join_request/<int:join_request_id>', methods=['POST'])
@login_required
def approve_join_request(join_request_id):
    join_request = JoinRequest.query.get_or_404(join_request_id)
    user = User.query.get(join_request.user_id)
    location = Location.query.get(join_request.location_id)

    # Check if the user is already associated with the location
    if user not in location.members:
        # Associate user with the location if not already associated
        location.members.append(user)
        flash('Join request approved and user added to location successfully!', 'success')
    else:
        flash('User is already a member of this location.', category='info')

    # Update the status of the join request
    join_request.status = 'approved'
    
    # Commit changes to the database
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Failed to approve join request due to a database error.', 'error')

    return redirect(url_for('dash.dashboard'))

@org.route('/decline_join_request/<int:join_request_id>', methods=['POST'])
@login_required
def decline_join_request(join_request_id):
    join_request = JoinRequest.query.get_or_404(join_request_id)

    # Update join request status to 'declined' instead of deleting it
    join_request.status = 'declined'
    db.session.commit()
    flash('Join request declined successfully!', 'success')
    return redirect(url_for('dash.dashboard'))

@org.route('/delete_join_request/<int:request_id>', methods=['POST'])
@login_required
def delete_join_request(request_id):
    join_request = JoinRequest.query.get_or_404(request_id)
    
    # Security check: Ensure that only authorized users can delete the request
    if join_request.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this request.', 'danger')
        return redirect(url_for('dash.dashboard'))
    
    db.session.delete(join_request)
    db.session.commit()
    flash('Join request deleted successfully!', 'success')
    return redirect(url_for('org.view_join_requests'))

@org.route('/view_join_requests')
@login_required
def view_join_requests():
    user_id = current_user.id  # Adjust as necessary to target the correct user or admin

    # Fetch all join requests with related organization and location
    join_requests = JoinRequest.query.options(
        joinedload(JoinRequest.organization),
        joinedload(JoinRequest.location)
    ).filter_by(user_id=user_id).all()

    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'request_status.html',
        join_requests=join_requests,
        nmae=current_user.username,
        is_admin=is_admin,
        is_member=user_locations
    )
@org.route('/delete_organization/<int:org_id>', methods=['POST', 'GET' ])
def delete_organization(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Check if the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("Unauthorized action.", category='danger')
        return redirect(url_for('org.dashboard'))

    db.session.delete(organization)
    db.session.commit()
    flash('Organization and all associated locations deleted successfully!', category='success')
    return redirect(url_for('org.manage_org'))