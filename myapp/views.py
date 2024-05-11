from flask import Blueprint,render_template
from flask_login import login_required,current_user
import uuid
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User,Organization,Location,QRCode,JoinRequest
import qrcode
from io import BytesIO
import base64
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import joinedload

views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')



@views.route('/dashboard/')
@login_required
def dashboard():
    user_id = current_user.id  # Get the current user's ID

    # Fetch organizations along with locations and join requests in a single query
    organizations = Organization.query.options(
        joinedload(Organization.locations),
        joinedload(Organization.join_requests)
    ).filter_by(user_id=user_id).all()

    organization_count = len(organizations)
    location_count = sum(len(org.locations) for org in organizations)
    join_requests = [request for org in organizations for request in org.join_requests]


    return render_template(
        'dashboard_base.html',
        name=current_user.username,
        organization_count=organization_count,
        location_count=location_count,
        organizations=organizations,
        join_requests=join_requests,
        location=Location
    )

@views.route("/create_org", methods=['GET', 'POST'])
@login_required
def create_org():
    if request.method == 'POST':
        name = request.form.get('name').strip().upper()  # Strip whitespace for consistent comparison
        user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
        
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

    organizations = Organization.query.filter_by(user_id=current_user.id).all()
    return render_template(
        'manage_org.html',
          organizations=organizations,
          name=current_user.username
          )


@views.route("/join_org", methods=['GET', 'POST'])
@login_required
def join_org():
    if request.method == 'POST':
        code = request.form.get('code')
        organization = Organization.query.filter_by(code=code).first()
        if organization:
            locations = Location.query.filter_by(organization_id=organization.id).all()
            return render_template('join_org.html', organization=organization, locations=locations)
        else:
            flash('No organization found with the provided code..', category='warning')
            return redirect(url_for('views.join_org'))
    return render_template('join_org.html', name=current_user.username)

@views.route('/join_request/<int:organization_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('views.dashboard'))

    return redirect(url_for('views.dashboard'))

@views.route('/approve_join_request/<int:join_request_id>', methods=['POST'])
@login_required
def approve_join_request(join_request_id):
    join_request = JoinRequest.query.get_or_404(join_request_id)
    join_request.status = 'approved'
    db.session.commit()
    flash('Join request approved successfully!', 'success')
    return redirect(url_for('views.dashboard'))

@views.route('/decline_join_request/<int:join_request_id>', methods=['POST'])
@login_required
def decline_join_request(join_request_id):
    join_request = JoinRequest.query.get_or_404(join_request_id)
    db.session.delete(join_request)
    db.session.commit()
    flash('Join request declined successfully!', 'success')
    return redirect(url_for('views.dashboard'))

@views.route('/view_join_requests')
@login_required
def view_join_requests():
    user_id = current_user.id  # Get the current user's ID

    # Fetch join requests with related organization and location
    join_requests = JoinRequest.query.options(
        joinedload(JoinRequest.organization).joinedload(Organization.locations)
    ).filter_by(user_id=user_id).all()

    return render_template(
        'request_status.html',
        join_requests=join_requests
    )

@views.route('/add_location/<int:org_id>', methods=['POST','GET'])
def add_location(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Security check to ensure the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("You do not have permission to add locations to this organization.", category='danger')
        return redirect(url_for('views.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        alias = request.form.get('alias')
        longitude = request.form.get('longitude')
        latitude = request.form.get('latitude')

        if not longitude or not latitude:
            flash("Please set coordinates.", category='danger')
            return redirect(url_for('views.add_location', org_id=org_id))


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
    return render_template(
        'add_location.html',
        org_id=org_id,
        name=current_user.username,
        organization=organization,
        locations=locations
    )

@views.route('/manage_location/<int:org_id>')
@login_required
def manage_locations(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Ensure the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("You are not authorized to view these locations.", category='danger')
        return redirect(url_for('views.dashboard'))

    locations = Location.query.filter_by(organization_id=organization.id).all()  # Use the organization's ID
    return render_template(
        'manage_locations.html',
        organization=organization,
        locations=locations,
        name=current_user.username
    )

@views.route('/delete_organization/<int:org_id>', methods=['POST', 'GET' ])
def delete_organization(org_id):
    organization = Organization.query.get_or_404(org_id)
    # Check if the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("Unauthorized action.", category='danger')
        return redirect(url_for('views.dashboard'))

    db.session.delete(organization)
    db.session.commit()
    flash('Organization and all associated locations deleted successfully!', category='success')
    return redirect(url_for('views.manage_org'))

@views.route('/generate_qr/<int:location_id>', methods=['GET', 'POST'])
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

    return render_template(
        'generated.html',
        qr_data=qr.qr_data,
        qr_image=qr_img_base64,
        location=location,
        organization=organization
    )



@views.route('/regenerate_qr/<int:location_id>', methods=['POST','GET'])
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

    return render_template(
        'generated.html',
        qr_data=qr.qr_data,
        qr_image=qr_img_base64,
        location=location,
        organization=organization
    )