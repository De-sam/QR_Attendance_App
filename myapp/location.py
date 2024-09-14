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

loc = Blueprint("loc", __name__)

@loc.route('/remove_member/<int:user_id>/<int:location_id>', methods=['POST'])
@login_required
def remove_member(user_id, location_id):
    # Security check to ensure only authorized users can make changes
    if not current_user.is_admin:
        flash('Unauthorized operation.', 'danger')
        return redirect(url_for('dash.dashboard'))

    # Get the location and the user based on IDs provided
    location = Location.query.get_or_404(location_id)
    user_to_remove = User.query.get_or_404(user_id)
    
    # Remove the user from the location
    if user_to_remove in location.members:
        location.members.remove(user_to_remove)
        db.session.commit()
        flash('Member successfully removed from the location.', 'success')
    else:
        flash('Member not found in this location.', 'warning')

    return redirect(url_for('dash.dashboard'))



@loc.route('/add_location/<int:org_id>', methods=['POST','GET'])
def add_location(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Security check to ensure the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("You do not have permission to add locations to this organization.", category='danger')
        return redirect(url_for('dash.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        alias = request.form.get('alias')
        longitude = request.form.get('longitude')
        latitude = request.form.get('latitude')

        if not longitude or not latitude:
            flash("Please set coordinates.", category='danger')
            return redirect(url_for('loc.add_location', org_id=org_id))


        # Check if the location already exists
        existing_location = Location.query.filter_by(address=address, alias=alias, longitude=longitude, latitude=latitude).first()
        if existing_location:
            flash('Location with this address, alias, longitude, and latitude already exists.', category='warning')
        else:
            # Create and save the new location
            new_location = Location(
                name=name,
                address=address,
                alias=alias,
                longitude=longitude,
                latitude=latitude,
                organization_id=organization.id  # Use the organization's ID
            )
            db.session.add(new_location)
            db.session.commit()
            flash('Location was added successfully!', category='success')

    locations = Location.query.filter_by(organization_id=org_id).all()
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'add_location.html',
        org_id=org_id,
        name=current_user.username,
        organization=organization,
        locations=locations,
        is_admin=is_admin,
        is_member=user_locations
    )

@loc.route('/delete_location/<int:location_id>', methods=['POST'])
@login_required
def delete_location(location_id):
    # Get the location by ID and ensure it exists
    location = Location.query.get_or_404(location_id)
    organization = Organization.query.get_or_404(location.organization_id)

    # Security check to ensure the current user is authorized to delete the location
    if organization.user_id != current_user.id:
        flash('Unauthorized operation.', 'danger')
        return redirect(url_for('dash.dashboard'))

    try:
        # Delete the location
        db.session.delete(location)
        db.session.commit()
        flash('Location deleted successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Error occurred while deleting the location.', 'danger')

    return redirect(url_for('loc.manage_locations', org_id=organization.id))

@loc.route('/manage_location/<int:org_id>')
@login_required
def manage_locations(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Ensure the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("You are not authorized to view these locations.", category='danger')
        return redirect(url_for('dash.dashboard'))

    locations = Location.query.filter_by(organization_id=organization.id).all()  # Use the organization's ID
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'manage_locations.html',
        organization=organization,
        locations=locations,
        name=current_user.username,
        is_admin=is_admin,
        is_member=user_locations
    )

@loc.route('/generate_qr/<int:location_id>', methods=['GET', 'POST'])
@login_required
def generate_qr(location_id):
    # Retrieve the location by ID and ensure it exists
    location = Location.query.get_or_404(location_id)
    organization = Organization.query.get(location.organization_id)

    # Check if a QR code already exists for this location
    qr = QRCode.query.filter_by(location_id=location_id).first()

    if not qr:
        # Construct QR data using all location details and include tolerance
        qr_data = (
            f"Name: {location.name}, "
            f"Address: {location.address}, "
            f"Alias: {location.alias}, "
            f"Organization: {organization.name}, "  # Include the organization name
            f"Latitude: {location.latitude}, "
            f"Longitude: {location.longitude}, "
            f"Tolerance: 100"
        )

        # Generate QR code
        img = qrcode.make(qr_data)

        # Create a new QRCode object and store it in the database
        new_qr = QRCode(qr_data=qr_data, location_id=location_id)
        db.session.add(new_qr)
        db.session.commit()
        qr = new_qr
    else:
        # Generate the QR code from the stored data
        img = qrcode.make(qr.qr_data)

    # Save the QR code image to a BytesIO buffer and modify it
    with BytesIO() as img_bytes:
        img.save(img_bytes)
        img_bytes.seek(0)

        # Load the image and prepare to draw text
        with Image.open(img_bytes) as qr_img:
            draw = ImageDraw.Draw(qr_img)
            font = ImageFont.truetype('myapp/static/fonts/SedanSC-Regular.ttf', size=20)

            # Prepare the texts
            org_text = organization.name
            alias_text = location.alias
            
            # Measure text sizes
            org_text_width, _, _, org_text_height = draw.textbbox((0, 0), org_text, font=font)
            alias_text_width, _, _, alias_text_height = draw.textbbox((0, 0), alias_text, font=font)

            # Calculate positions for placing the organization name at the top
            padding = 10  # Space from the top and bottom of the image

            # Place the organization name at the top, centered
            text_x_org = (qr_img.width - org_text_width) // 2  # Center the organization name
            text_y_org = padding  # Position the organization name at the top

            # Place the alias at the bottom, centered
            text_x_alias = (qr_img.width - alias_text_width) // 2  # Center the alias at the bottom
            text_y_alias = qr_img.height - alias_text_height - padding  # Position alias near the bottom

            # Draw the organization name at the top
            draw.text((text_x_org, text_y_org), org_text, fill='black', font=font)
            # Draw the alias at the bottom
            draw.text((text_x_alias, text_y_alias), alias_text, fill='black', font=font)

            # Save the modified QR code image to a new BytesIO buffer
            qr_img_bytes = BytesIO()
            qr_img.save(qr_img_bytes, format='PNG')
            qr_img_bytes.seek(0)
            qr_img_base64 = base64.b64encode(qr_img_bytes.read()).decode('utf-8')
    
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'generated.html',
        qr_data=qr.qr_data,
        qr_image=qr_img_base64,
        location=location,
        organization=organization,
        name=current_user.username,
        is_admin=is_admin,
        is_member=user_locations
    )



@loc.route('/set_deadline/<int:location_id>', methods=['GET', 'POST'])
@login_required
def set_deadline(location_id):
    location = Location.query.get_or_404(location_id)
    if request.method == 'POST':
        deadline_time = request.form.get('deadline')
        location.deadline = datetime.strptime(deadline_time, '%H:%M').time()
        db.session.commit()
        flash('Deadline updated successfully!', 'success')
        return redirect(url_for('loc.set_deadline', location_id=location.id))
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template('set_deadline.html',
                            location=location,
                            name=current_user.username,
                            is_admin=is_admin,
                            is_member=user_locations
                            )

@loc.route('/set_closing_time/<int:location_id>', methods=['GET', 'POST'])
@login_required
def set_closing_time(location_id):
    location = Location.query.get_or_404(location_id)
    if request.method == 'POST':
        closing_time = request.form.get('closing_time')
        location.closing_time = datetime.strptime(closing_time, '%H:%M').time()
        db.session.commit()
        flash('Closing time updated successfully!', 'success')
        return redirect(url_for('loc.set_closing_time', location_id=location.id))
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template('set_closing_time.html',
                            location=location,
                            name=current_user.username,
                            is_admin=is_admin,
                            is_member=user_locations
                            )


@loc.route('/regenerate_qr/<int:location_id>', methods=['POST','GET'])
@login_required
def regenerate_qr(location_id):
    location = Location.query.get_or_404(location_id)
    organization = Organization.query.get(location.organization_id)
    qr = QRCode.query.filter_by(location_id=location.id).first()  # Use the location's ID

    if qr:
        db.session.delete(qr)
        db.session.commit()

    if not qr:
        # Construct QR data using all location details and include tolerance
        qr_data = (
            f"Name: {location.name}, "
            f"Address: {location.address}, "
            f"Alias: {location.alias}, "
            f"Latitude: {location.latitude}, "
            f"Longitude: {location.longitude}, "
            f"Tolerance: 100"  # Tolerance in meters
        )

        # Generate QR code
        img = qrcode.make(qr_data)

        # Create a new QRCode object and store it in the database
        new_qr = QRCode(qr_data=qr_data, location_id=location_id)
        db.session.add(new_qr)
        db.session.commit()
        qr = new_qr
    else:
        # Generate the QR code from the stored data
        img = qrcode.make(qr.qr_data)

    # Save the QR code image to a BytesIO buffer and modify it
    with BytesIO() as img_bytes:
        img.save(img_bytes)
        img_bytes.seek(0)

        # Load the image and prepare to draw text
        with Image.open(img_bytes) as qr_img:
            draw = ImageDraw.Draw(qr_img)
            font = ImageFont.truetype('myapp/static/fonts/SedanSC-Regular.ttf', size=20)

            # Measure text size for accurate placement
            text_width, _, _, text_height = draw.textbbox((0, 0), location.alias, font=font)
            text_x = (qr_img.width - text_width) // 2
            text_y = qr_img.height - text_height - 10

            # Draw the alias text on the QR code image
            draw.text((text_x, text_y), location.alias, fill='black', font=font)

            # Save the modified QR code image to a new BytesIO buffer
            qr_img_bytes = BytesIO()
            qr_img.save(qr_img_bytes, format='PNG')
            qr_img_bytes.seek(0)
            qr_img_base64 = base64.b64encode(qr_img_bytes.read()).decode('utf-8')
    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'generated.html',
        qr_data=qr.qr_data,
        qr_image=qr_img_base64,
        location=location,
        organization=organization,
        name=current_user.username,
        is_admin=is_admin,
        is_member=user_locations
    )

