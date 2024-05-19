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





views = Blueprint("views", __name__)

@views.before_request
def before_request():
    session.permanent = True
    session.modified = True
    permanent_session_lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']
    if 'last_activity' in session:
        now = datetime.now(timezone.utc)
        last_activity = session['last_activity']
        session['last_activity'] = now
        if now - last_activity > permanent_session_lifetime:
            flash('Session timed out due to inactivity.', 'warning')
            return redirect(url_for('auth.logout'))
    else:
        session['last_activity'] = datetime.now(timezone.utc)


@views.route("/")
@views.route("/home")
def home():
    return render_template('index.html')



@views.route('/dashboard/')
@login_required
def dashboard():
    user_id = current_user.id 
    search_query = request.args.get('search', '').strip()
    user = current_user
   
   # Determine if the user is an admin
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0

    search_query = request.args.get('search', '').strip()

    user = User.query.filter_by(id=user_id).first()



   
    organizations = Organization.query.options(
        joinedload(Organization.locations),
        joinedload(Organization.join_requests).joinedload(JoinRequest.location)
    ).filter_by(user_id=user_id).all()

    # Filter join requests to only include pending ones for display in the dashboard
    pending_join_requests = [request for org in organizations for request in org.join_requests if request.status == 'pending']

     # Only prepare member details if there are locations within these organizations
    member_details = []
    if any(org.locations for org in organizations):
        for org in organizations:
            for location in org.locations:
                for member in location.members:
                     if search_query == '' or search_query.lower() in member.username.lower():
                        member_details.append({
                        'id': member.id, 
                        'name': member.username,
                        'email': member.email,
                        'alias': location.alias,
                        'organization_name': org.name,
                        'location_id': location.id
                    })

    organization_count = len(organizations)
    location_count = sum(len(org.locations) for org in organizations)

    has_results = bool(member_details)

    # Get the current date
    today = date.today()
    
    # Get the locations the current user is a member of
    user_locations = current_user.locations
    
    # Query to get today's attendance records for user's locations
    today_attendance = Attendance.query.filter(
        db.func.date(Attendance.clock_in_time) == today,
        Attendance.location.has(Location.members.contains(current_user))
    ).all()
    
    total_members = len(member_details)

    # Calculate the number of present and absent members
    total_present = sum(1 for record in today_attendance if record.is_clocked_in or record.clock_out_time is not None)
    
    total_absent= total_members - total_present

    return render_template(
        'dashboard_base.html',
        name=current_user.username,
        organization_count=organization_count,
        location_count=location_count,
        organizations=organizations,
        join_requests=pending_join_requests,
        member_details=member_details if member_details else None,
        location=Location,
        has_results=has_results,
        total_present=total_present,
        total_absent=total_absent,
        is_admin=is_admin,
        is_member=member_details
    )


@views.route('/admin_only/')
@login_required
def admin_only_function():
    if not current_user.is_admin:
        flash('Unauthorized operation. Admin rights required.', 'danger')
        return redirect(url_for('views.dashboard'))

    # Proceed with admin-only functionality
    ...

@views.route("/clock_in", methods=['GET', 'POST'])
@login_required
def clock_in():
    return render_template('clock_in.html', name=current_user.username)


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
            return redirect(url_for('views.create_organization'))

        if not current_user.is_admin:
            current_user.is_admin = True
            flash('You have been granted admin rights.', category='info')
        

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

    return redirect(url_for('views.dashboard'))

@views.route('/decline_join_request/<int:join_request_id>', methods=['POST'])
@login_required
def decline_join_request(join_request_id):
    join_request = JoinRequest.query.get_or_404(join_request_id)

    # Update join request status to 'declined' instead of deleting it
    join_request.status = 'declined'
    db.session.commit()
    flash('Join request declined successfully!', 'success')
    return redirect(url_for('views.dashboard'))

@views.route('/remove_member/<int:user_id>/<int:location_id>', methods=['POST'])
@login_required
def remove_member(user_id, location_id):
    # Security check to ensure only authorized users can make changes
    if not current_user.is_admin:
        flash('Unauthorized operation.', 'danger')
        return redirect(url_for('views.dashboard'))

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

    return redirect(url_for('views.dashboard'))

@views.route('/delete_join_request/<int:request_id>', methods=['POST'])
@login_required
def delete_join_request(request_id):
    join_request = JoinRequest.query.get_or_404(request_id)
    
    # Security check: Ensure that only authorized users can delete the request
    if join_request.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this request.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    db.session.delete(join_request)
    db.session.commit()
    flash('Join request deleted successfully!', 'success')
    return redirect(url_for('views.view_join_requests'))

@views.route('/view_join_requests')
@login_required
def view_join_requests():
    user_id = current_user.id  # Adjust as necessary to target the correct user or admin

    # Fetch all join requests with related organization and location
    join_requests = JoinRequest.query.options(
        joinedload(JoinRequest.organization),
        joinedload(JoinRequest.location)
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
        organization=organization,
        name=current_user.username
    )

@views.route('/set_deadline/<int:location_id>', methods=['GET', 'POST'])
@login_required
def set_deadline(location_id):
    location = Location.query.get_or_404(location_id)
    if request.method == 'POST':
        deadline_time = request.form.get('deadline')
        location.deadline = datetime.strptime(deadline_time, '%H:%M').time()
        db.session.commit()
        flash('Deadline updated successfully!', 'success')
        return redirect(url_for('views.set_deadline', location_id=location.id))

    return render_template('set_deadline.html', location=location,name=current_user.username)

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
        organization=organization,
        name=current_user.username
    )

@views.route('/pre', methods=['GET', 'POST'])
@login_required
def pre():
    # Adjust this to check for clock-in status based on current day
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.clock_in_time >= today_start,
        Attendance.clock_in_time < today_end
    ).order_by(Attendance.clock_in_time.desc()).first()

    if attendance and not attendance.clock_out_time:
        action = "Clock Out"
        url = url_for('views.clock_in')
    else:
        action = "Clock In"
        url = url_for('views.clock_in')

    return render_template('pre-clockin.html'
                           , action=action,
                             url=url,
                             name=current_user.username
                             )

@views.route('/process_qr_code', methods=['POST', 'GET'])
@login_required
def process_qr_code():
    qr_code_data = request.form.get('qrCodeData')
    
    # Check if latitude and longitude data are provided
    lat_data = request.form.get('latitude')
    lng_data = request.form.get('longitude')
    if not lat_data or not lng_data:
        flash('Please set coordinates.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    try:
        # Convert latitude and longitude to float
        lat = float(lat_data)
        lng = float(lng_data)
        print(f"Received coordinates: Latitude: {lat}, Longitude: {lng}")
    except ValueError:
        flash('Invalid coordinates.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    current_coords = (lat, lng)
    
    # Parse and validate QR code data
    qr_code = QRCode.query.filter_by(qr_data=qr_code_data).first()
    if not qr_code:
        flash('QR Code not recognized.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    location = Location.query.get(qr_code.location_id)
    if not location:
        flash('No location associated with this QR code.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    print(f"Location coordinates: Latitude: {location.latitude}, Longitude: {location.longitude}")
    
    # Check if the current user is associated with the location
    if current_user not in location.members:
        flash('You are not authorized to perform this action at this location.', 'danger')
        return redirect(url_for('views.dashboard'))
    
    # Get the user's timezone
    if current_user.timezone:
        tz = pytz.timezone(current_user.timezone)
    else:
        tz = pytz.utc

    current_time = datetime.now(tz)
    print(f"Current time in user's timezone: {current_time}")

    # Distance validation using Haversine
    # location_coords = (location.latitude, location.longitude)
    # distance = haversine(current_coords, location_coords, unit=Unit.METERS)
    # print(f"Calculated distance: {distance} meters")
    # if distance > 500:
    #     flash(f'Not within the required range of the location. Distance: {distance:.2f} meters', 'danger')
    #     return redirect(url_for('views.pre')

    if current_user.timezone:
        tz = pytz.timezone(current_user.timezone)
        c_time = datetime.now(tz)
    else:
        c_time = datetime.now(pytz.utc)


    # Check deadline and set status
    if location.deadline:
        deadline_time = location.deadline
        deadline_datetime = datetime.combine(c_time.date(), deadline_time, tzinfo=c_time.tzinfo)
    else:
        deadline_datetime = None

    # Check deadline and set status
    if deadline_datetime is None:
        status = 'Dead line not set'
    elif c_time <= deadline_datetime:
        status = 'Early'
    else:
        status = 'Late'
    
    
    

    # Find if there's an open attendance record
    attendance = Attendance.query.filter_by(user_id=current_user.id, location_id=location.id, is_clocked_in=True).first()
    if attendance:
        attendance.clock_out_time = current_time
        attendance.is_clocked_in = False
        flash(f'Successfully clock-out at {current_time.strftime("%I:%M:%S %p %Z")}.Goodbye!!!', 'success')
    else:
        new_attendance = Attendance(
            user_id=current_user.id,
            location_id=location.id,
            clock_in_time=current_time,
            is_clocked_in=True,
            status=status
        )
        db.session.add(new_attendance)
        flash(f'Clock-in successful. You arrived at {current_time.strftime("%I:%M:%S %p %Z")} ({status}).', 'success')
    db.session.commit()
    
    return redirect(url_for('views.dashboard'))

@views.route('/attendance_log', methods=['GET', 'POST'])
@login_required
def attendance_log():
    organizations = Organization.query.filter_by(user_id=current_user.id).all()
    selected_org_id = request.args.get('organization_id')
    selected_location_id = request.args.get('location_id')
    selected_status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    download = request.args.get('download')

    if selected_org_id and selected_location_id:
        query = Attendance.query.join(Location).filter(
            Attendance.location_id == selected_location_id,
            Location.organization_id == selected_org_id
        )
    elif selected_org_id:
        query = Attendance.query.join(Location).filter(
            Location.organization_id == selected_org_id
        )
    else:
        query = Attendance.query

    if selected_status:
        query = query.filter(Attendance.status == selected_status)

    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Attendance.clock_in_time >= start_date_obj)

    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(Attendance.clock_in_time <= end_date_obj)

    attendances = query.all()

    
     # Get user's current timezone
    user_timezone = current_user.timezone    

   
    
    if current_user.timezone:
        tz = pytz.timezone(current_user.timezone)
        current_time = datetime.now(tz)
    else:
        current_time = datetime.now(pytz.utc)

    user_timezone = current_user.timezone
    if user_timezone:
        user_tz = pytz.timezone(user_timezone)
    else:
        user_tz = pytz.utc

    if not selected_org_id and not selected_location_id:
        # No organization selected, so no attendance records to display
        return render_template('attendance_log.html',
                               organizations=organizations,
                               selected_org_id=selected_org_id,
                               selected_location_id=selected_location_id,
                               attendances=attendances,
                               name=current_user.username,
                               timezone= user_timezone,
                               current_date=current_time.strftime('%d-%m-%Y'),
                               current_time=current_time.strftime('%I:%M:%S %p %Z')
                               )

    # Convert attendance times to user's local timezone
    if attendances:
        for attendance in attendances:
            attendance.clock_in_time = attendance.clock_in_time.astimezone(user_tz)
            if attendance.clock_out_time:
                attendance.clock_out_time = attendance.clock_out_time.astimezone(user_tz)
    
    import pdfkit
    if download == 'pdf':
        html = render_template('attendance_pdf.html', attendances=attendances, user_timezone=current_user.timezone)
        pdf = pdfkit.from_string(html, False)
        response = BytesIO(pdf)
        response.seek(0)
        return send_file(response, mimetype='application/pdf', as_attachment=True, download_name='attendance.pdf')


    selected_status = request.args.get('status')
    selected_date = request.args.get('date')

    if selected_status:
            query = query.filter(Attendance.status == selected_status)

    if selected_date:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
            query = query.filter(db.func.date(Attendance.clock_in_time) == date_obj)


    return render_template(
        'attendance_log.html',
        attendances=attendances,
        organizations=organizations,
        selected_org_id=selected_org_id,
        selected_location_id=selected_location_id,
        name=current_user.username,
        current_date=current_time.strftime('%d-%m-%Y'),
        current_time=current_time.strftime('%I:%M:%S %p %Z'),
        selected_status=selected_status,
        selected_date=selected_date,
        timezone= user_timezone
    )



TIMEZONES = [
    'Africa/Abidjan', 'Africa/Accra', 'Africa/Algiers', 'Africa/Bissau', 'Africa/Cairo', 'Africa/Casablanca',
    'Africa/Ceuta', 'Africa/El_Aaiun', 'Africa/Johannesburg', 'Africa/Juba', 'Africa/Khartoum', 'Africa/Lagos',
    'Africa/Maputo', 'Africa/Monrovia', 'Africa/Nairobi', 'Africa/Ndjamena', 'Africa/Tripoli', 'Africa/Tunis',
    'Africa/Windhoek', 'America/Adak', 'America/Anchorage', 'America/Araguaina', 'America/Argentina/Buenos_Aires',
    'America/Argentina/Catamarca', 'America/Argentina/Cordoba', 'America/Argentina/Jujuy', 'America/Argentina/La_Rioja',
    'America/Argentina/Mendoza', 'America/Argentina/Rio_Gallegos', 'America/Argentina/Salta', 'America/Argentina/San_Juan',
    'America/Argentina/San_Luis', 'America/Argentina/Tucuman', 'America/Argentina/Ushuaia', 'America/Asuncion',
    'America/Atikokan', 'America/Bahia', 'America/Bahia_Banderas', 'America/Barbados', 'America/Belem', 'America/Belize',
    'America/Blanc-Sablon', 'America/Boa_Vista', 'America/Bogota', 'America/Boise', 'America/Cambridge_Bay',
    'America/Campo_Grande', 'America/Cancun', 'America/Caracas', 'America/Cayenne', 'America/Chicago', 'America/Chihuahua',
    'America/Costa_Rica', 'America/Creston', 'America/Cuiaba', 'America/Curacao', 'America/Danmarkshavn', 'America/Dawson',
    'America/Dawson_Creek', 'America/Denver', 'America/Detroit', 'America/Edmonton', 'America/Eirunepe', 'America/El_Salvador',
    'America/Fort_Nelson', 'America/Fortaleza', 'America/Glace_Bay', 'America/Godthab', 'America/Goose_Bay', 'America/Grand_Turk',
    'America/Guatemala', 'America/Guayaquil', 'America/Guyana', 'America/Halifax', 'America/Havana', 'America/Hermosillo',
    'America/Indiana/Indianapolis', 'America/Indiana/Knox', 'America/Indiana/Marengo', 'America/Indiana/Petersburg',
    'America/Indiana/Tell_City', 'America/Indiana/Vevay', 'America/Indiana/Vincennes', 'America/Indiana/Winamac',
    'America/Inuvik', 'America/Iqaluit', 'America/Jamaica', 'America/Juneau', 'America/Kentucky/Louisville',
    'America/Kentucky/Monticello', 'America/La_Paz', 'America/Lima', 'America/Los_Angeles', 'America/Maceio', 'America/Managua',
    'America/Manaus', 'America/Martinique', 'America/Matamoros', 'America/Mazatlan', 'America/Menominee', 'America/Merida',
    'America/Metlakatla', 'America/Mexico_City', 'America/Miquelon', 'America/Moncton', 'America/Monterrey', 'America/Montevideo',
    'America/Nassau', 'America/New_York', 'America/Nipigon', 'America/Nome', 'America/Noronha', 'America/North_Dakota/Beulah',
    'America/North_Dakota/Center', 'America/North_Dakota/New_Salem', 'America/Nuuk', 'America/Ojinaga', 'America/Panama',
    'America/Pangnirtung', 'America/Paramaribo', 'America/Phoenix', 'America/Port-au-Prince', 'America/Port_of_Spain',
    'America/Porto_Velho', 'America/Puerto_Rico', 'America/Punta_Arenas', 'America/Rainy_River', 'America/Rankin_Inlet',
    'America/Recife', 'America/Regina', 'America/Resolute', 'America/Rio_Branco', 'America/Santarem', 'America/Santiago',
    'America/Santo_Domingo', 'America/Sao_Paulo', 'America/Scoresbysund', 'America/Sitka', 'America/St_Johns',
    'America/Swift_Current', 'America/Tegucigalpa', 'America/Thule', 'America/Thunder_Bay', 'America/Tijuana',
    'America/Toronto', 'America/Vancouver', 'America/Whitehorse', 'America/Winnipeg', 'America/Yakutat', 'America/Yellowknife',
    'Antarctica/Casey', 'Antarctica/Davis', 'Antarctica/DumontDUrville', 'Antarctica/Macquarie', 'Antarctica/Mawson',
    'Antarctica/McMurdo', 'Antarctica/Palmer', 'Antarctica/Rothera', 'Antarctica/Syowa', 'Antarctica/Troll', 'Antarctica/Vostok',
    'Arctic/Longyearbyen', 'Asia/Aden', 'Asia/Almaty', 'Asia/Amman', 'Asia/Anadyr', 'Asia/Aqtau', 'Asia/Aqtobe', 'Asia/Ashgabat',
    'Asia/Atyrau', 'Asia/Baghdad', 'Asia/Bahrain', 'Asia/Baku', 'Asia/Bangkok', 'Asia/Barnaul', 'Asia/Beirut', 'Asia/Bishkek',
    'Asia/Brunei', 'Asia/Chita', 'Asia/Choibalsan', 'Asia/Colombo', 'Asia/Damascus', 'Asia/Dhaka', 'Asia/Dili', 'Asia/Dubai',
    'Asia/Dushanbe', 'Asia/Famagusta', 'Asia/Gaza', 'Asia/Hebron', 'Asia/Ho_Chi_Minh', 'Asia/Hong_Kong', 'Asia/Hovd', 'Asia/Irkutsk',
    'Asia/Jakarta', 'Asia/Jayapura', 'Asia/Jerusalem', 'Asia/Kabul', 'Asia/Kamchatka', 'Asia/Karachi', 'Asia/Kathmandu',
    'Asia/Khandyga', 'Asia/Kolkata', 'Asia/Krasnoyarsk', 'Asia/Kuala_Lumpur', 'Asia/Kuching', 'Asia/Kuwait', 'Asia/Macau',
    'Asia/Magadan', 'Asia/Makassar', 'Asia/Manila', 'Asia/Muscat', 'Asia/Nicosia', 'Asia/Novokuznetsk', 'Asia/Novosibirsk',
    'Asia/Omsk', 'Asia/Oral', 'Asia/Phnom_Penh', 'Asia/Pontianak', 'Asia/Pyongyang', 'Asia/Qatar', 'Asia/Qostanay', 'Asia/Qyzylorda',
    'Asia/Riyadh', 'Asia/Sakhalin', 'Asia/Samarkand', 'Asia/Seoul', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Srednekolymsk',
    'Asia/Taipei', 'Asia/Tashkent', 'Asia/Tbilisi', 'Asia/Tehran', 'Asia/Thimphu', 'Asia/Tokyo', 'Asia/Tomsk', 'Asia/Ulaanbaatar',
    'Asia/Urumqi', 'Asia/Ust-Nera', 'Asia/Vientiane', 'Asia/Vladivostok', 'Asia/Yakutsk', 'Asia/Yangon', 'Asia/Yekaterinburg',
    'Asia/Yerevan', 'Atlantic/Azores', 'Atlantic/Bermuda', 'Atlantic/Canary', 'Atlantic/Cape_Verde', 'Atlantic/Faroe',
    'Atlantic/Madeira', 'Atlantic/Reykjavik', 'Atlantic/South_Georgia', 'Atlantic/St_Helena', 'Atlantic/Stanley',
    'Australia/Adelaide', 'Australia/Brisbane', 'Australia/Broken_Hill', 'Australia/Currie', 'Australia/Darwin',
    'Australia/Eucla', 'Australia/Hobart', 'Australia/Lindeman', 'Australia/Lord_Howe', 'Australia/Melbourne',
    'Australia/Perth', 'Australia/Sydney', 'Europe/Amsterdam', 'Europe/Andorra', 'Europe/Astrakhan', 'Europe/Athens',
    'Europe/Belgrade', 'Europe/Berlin', 'Europe/Bratislava', 'Europe/Brussels', 'Europe/Bucharest', 'Europe/Budapest',
    'Europe/Busingen', 'Europe/Chisinau', 'Europe/Copenhagen', 'Europe/Dublin', 'Europe/Gibraltar', 'Europe/Guernsey',
    'Europe/Helsinki', 'Europe/Isle_of_Man', 'Europe/Istanbul', 'Europe/Jersey', 'Europe/Kaliningrad', 'Europe/Kiev',
    'Europe/Kirov', 'Europe/Lisbon', 'Europe/Ljubljana', 'Europe/London', 'Europe/Luxembourg', 'Europe/Madrid', 'Europe/Malta',
    'Europe/Mariehamn', 'Europe/Minsk', 'Europe/Monaco', 'Europe/Moscow', 'Europe/Oslo', 'Europe/Paris', 'Europe/Podgorica',
    'Europe/Prague', 'Europe/Riga', 'Europe/Rome', 'Europe/Samara', 'Europe/San_Marino', 'Europe/Sarajevo', 'Europe/Saratov',
    'Europe/Simferopol', 'Europe/Skopje', 'Europe/Sofia', 'Europe/Stockholm', 'Europe/Tallinn', 'Europe/Tirane',
    'Europe/Ulyanovsk', 'Europe/Uzhgorod', 'Europe/Vaduz', 'Europe/Vatican', 'Europe/Vienna', 'Europe/Vilnius',
    'Europe/Volgograd', 'Europe/Warsaw', 'Europe/Zagreb', 'Europe/Zaporozhye', 'Europe/Zurich', 'Indian/Antananarivo',
    'Indian/Chagos', 'Indian/Christmas', 'Indian/Cocos', 'Indian/Comoro', 'Indian/Kerguelen', 'Indian/Mahe', 'Indian/Maldives',
    'Indian/Mauritius', 'Indian/Mayotte', 'Indian/Reunion', 'Pacific/Apia', 'Pacific/Auckland', 'Pacific/Bougainville',
    'Pacific/Chatham', 'Pacific/Chuuk', 'Pacific/Easter', 'Pacific/Efate', 'Pacific/Enderbury', 'Pacific/Fakaofo',
    'Pacific/Fiji', 'Pacific/Funafuti', 'Pacific/Galapagos', 'Pacific/Gambier', 'Pacific/Guadalcanal', 'Pacific/Guam',
    'Pacific/Honolulu', 'Pacific/Kiritimati', 'Pacific/Kosrae', 'Pacific/Kwajalein', 'Pacific/Majuro', 'Pacific/Marquesas',
    'Pacific/Midway', 'Pacific/Nauru', 'Pacific/Niue', 'Pacific/Norfolk', 'Pacific/Noumea', 'Pacific/Pago_Pago',
    'Pacific/Palau', 'Pacific/Pitcairn', 'Pacific/Pohnpei', 'Pacific/Port_Moresby', 'Pacific/Rarotonga', 'Pacific/Saipan',
    'Pacific/Tahiti', 'Pacific/Tarawa', 'Pacific/Tongatapu', 'Pacific/Wake', 'Pacific/Wallis', 'UTC'
]



@views.route('/set_timezone', methods=['GET', 'POST'])
@login_required
def set_timezone():
    if request.method == 'POST':
        timezone = request.form.get('timezone')

        # Validate timezone
        if timezone not in TIMEZONES:
            flash('Invalid timezone selected.', 'danger')
            return render_template('settings.html', timezones=TIMEZONES, user_timezone=current_user.timezone)

        # Save timezone to the user's profile
        current_user.set_timezone(timezone)
        db.session.commit()
        flash(f'Timezone set to {timezone} and saved successfully.', 'success')

        return redirect(url_for('views.dashboard'))

    # Get user's current timezone
    user_timezone = current_user.timezone

    return render_template(
        'settings.html',
        timezones=TIMEZONES,
        user_timezone=user_timezone,
        name=current_user.username
        )



def get_current_time():
    # Check if the user has a timezone set
    if current_user.timezone:
        # Get the user's timezone
        user_tz = pytz.timezone(current_user.timezone)
        
        # Get the current time in UTC
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        
        # Convert UTC time to the user's timezone
        local_time = utc_time.astimezone(user_tz)
        
        # Format the time as needed
        current_time = local_time.strftime('%I:%M:%S %p')
    else:
        # Default to UTC time if no timezone is set
        current_time = datetime.now(pytz.utc).strftime('%I:%M:%S %p')
    
    return current_time
