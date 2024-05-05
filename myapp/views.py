from flask import Blueprint,render_template
from flask_login import login_required,current_user
import uuid
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User,Organization,Location,QRCode
import qrcode
from io import BytesIO
import base64



views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')



@views.route("/dashboard")
@login_required
def dashboard():
    user_id = current_user.id  # Get the current user's ID
    # Fetch organizations and locations belonging to the current user
    organizations = Organization.query.filter_by(user_id=user_id).all()
    organization_count = len(organizations)

    locations = Location.query.join(Organization).filter(Organization.user_id == user_id).all()
    location_count = len(locations)

    organizations = Organization.query.all()    
    return render_template(
        'dashboard_base.html', 
        name=current_user.username,
        organization_count=organization_count,
        organizations=organizations,
        location_count=location_count,
        locations=locations
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

    organizations = Organization.query.filter_by(user_id=current_user.id).all()
    return render_template(
        'manage_org.html',
          organizations=organizations,
          name=current_user.username
          )



@views.route("/join_org")
@login_required
def join_org():
    return render_template('join_org.html', name=current_user.username)


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
            flash('Please set coordinates.', category='warning')
            return render_template(
                'add_location.html',
                org_id=org_id,
                organization=organization,
                longitude=longitude,
                latitude=latitude
            )

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
                organization_id=org_id  # assuming you have a relationship set up
            )
            db.session.add(new_location)
            db.session.commit()
            flash('Location was added and its corresponding QR-Code was generated successfully view locations to download QR-Code', category='success')
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
    # Check if the organization belongs to the current user
    if organization.user_id != current_user.id:
        flash("Unauthorized action.", category='danger')
        return redirect(url_for('views.dashboard'))

    db.session.delete(organization)
    db.session.commit()
    flash('Organization and all associated locations deleted successfully!', category='success')
    return redirect(url_for('views.manage_org'))

@views.route('/generate_qr/<int:location_id>',methods=['GET','POST'])
@login_required
def generate_qr(location_id):
    # Retrieve the location by ID and ensure it exists
    location = Location.query.get_or_404(location_id)
    organization = Organization.query.get(location.organization_id)
    # Check if a QR code already exists for this location
    qr = QRCode.query.filter_by(location_id=location_id).first()

    if not qr:
        # Construct QR data using all location details
        qr_data = (
            f"Name: {location.name}, "
            f"Address: {location.address}, "
            f"Alias: {location.alias}, "
            f"Latitude: {location.latitude}, "
            f"Longitude: {location.longitude}"
        )
        
        # Generate QR code
        img = qrcode.make(qr_data)

        # Create a new QRCode object and store it in the database
        new_qr = QRCode(qr_data=qr_data, location_id=location_id)
        db.session.add(new_qr)
        db.session.commit()
        qr = new_qr
    else:
        # If a QR code already exists, generate it from the stored data
        img = qrcode.make(qr.qr_data)

    # Save the QR code image to a BytesIO buffer
    img_bytes = BytesIO()
    img.save(img_bytes)
    img_bytes.seek(0)
    img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')
    
    return render_template(
        'generated.html',
        qr_data=qr.qr_data,
        qr_image=img_base64,
        location=location,
        organization=organization
    )
    
@views.route('/delete_qr/<int:location_id>', methods=['POST','GET'])
@login_required
def delete_qr(location_id):
    qr = QRCode.query.filter_by(location_id=location_id).first()
    if qr:
        db.session.delete(qr)
        db.session.commit()
        flash('QR code deleted successfully!', category='success')
    return redirect(url_for('views.generate_qr', location_id=location_id))

@views.route('/regenerate_qr/<int:location_id>', methods=['POST','GET'])
@login_required
def regenerate_qr(location_id):
    location = Location.query.get_or_404(location_id)
    qr = QRCode.query.filter_by(location_id=location_id).first()

    if qr:
        db.session.delete(qr)
        db.session.commit()

    # Generate new QR code
    qr_data = (
        f"Name: {location.name}, "
        f"Address: {location.address}, "
        f"Alias: {location.alias}, "
        f"Latitude: {location.latitude}, "
        f"Longitude: {location.longitude}"
    )
    img = qrcode.make(qr_data)
    new_qr = QRCode(qr_data=qr_data, location_id=location_id)
    db.session.add(new_qr)
    db.session.commit()

    # Convert to base64
    img_bytes = BytesIO()
    img.save(img_bytes)
    img_bytes.seek(0)
    img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')

    flash('QR code regenerated successfully!', category='success')
    return render_template(
        'generated.html',
        qr_data=new_qr.qr_data,
        qr_image=img_base64,
        location=location
    )

