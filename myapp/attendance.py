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

attend = Blueprint("attend", __name__)

@attend.route("/clock_in", methods=['GET', 'POST'])
@login_required
def clock_in():
    user_id = current_user.id
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template('clock_in.html',
                            name=current_user.username,
                            is_admin=is_admin,
                            is_member=user_locations
                            )


@attend.route('/pre', methods=['GET', 'POST'])
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
        url = url_for('org.clock_in')
    else:
        action = "Clock In"
        url = url_for('attend.clock_in')

    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template('pre-clockin.html'
                           , action=action,
                             url=url,
                             name=current_user.username,
                             is_admin=is_admin,
                            is_member=user_locations
                             )

@attend.route('/process_qr_code', methods=['POST', 'GET'])
@login_required
def process_qr_code():
    qr_code_data = request.form.get('qrCodeData')

    # Check if latitude and longitude data are provided
    lat_data = request.form.get('latitude')
    lng_data = request.form.get('longitude')
    if not lat_data or not lng_data:
        flash('Please set coordinates.', 'danger')
        return redirect(url_for('attend.clock_in'))

    try:
        # Convert latitude and longitude to float
        lat = float(lat_data)
        lng = float(lng_data)
        print(f"Received coordinates: Latitude: {lat}, Longitude: {lng}")
    except ValueError:
        flash('Invalid coordinates.', 'danger')
        return redirect(url_for('attend.clock_in'))

    current_coords = (lat, lng)

    # Parse and validate QR code data
    qr_code = QRCode.query.filter_by(qr_data=qr_code_data).first()
    if not qr_code:
        flash('QR Code not recognized.', 'danger')
        return redirect(url_for('attend.clock_in'))

    location = Location.query.get(qr_code.location_id)
    if not location:
        flash('No location associated with this QR code.', 'danger')
        return redirect(url_for('attend.clock_in'))

    print(f"Location coordinates: Latitude: {location.latitude}, Longitude: {location.longitude}")

    # Check if the current user is associated with the location
    if current_user not in location.members:
        flash('You are not authorized to perform this action at this location.', 'danger')
        return redirect(url_for('attend.clock_in'))

    # Get the user's timezone
    tz = pytz.timezone(current_user.timezone) if current_user.timezone else pytz.utc
    current_time = datetime.now(tz)
    print(f"Current time in user's timezone: {current_time}")

    # Check if the user is within 100 meters of the coordinates in the QR code
    # import math
    # def haversine(lat1, lon1, lat2, lon2):
    #     R = 6371000  # Radius of the Earth in meters
    #     phi1 = math.radians(lat1)
    #     phi2 = math.radians(lat2)
    #     delta_phi = math.radians(lat2 - lat1)
    #     delta_lambda = math.radians(lon2 - lon1)
    #     a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    #     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    #     return R * c

    # distance = haversine(lat, lng, location.latitude, location.longitude)
    # if distance > 100:
    #     flash(f'You are not within the required range of the location. Distance: {distance:.2f} meters', 'danger')
    #     return redirect(url_for('attend.clock_in'))
    # else:
    #     flash(f'Within the required range of the location. Distance: {distance:.2f} meters', 'info')

    # Check deadline and set status
    c_time = current_time
    if location.deadline:
        deadline_time = location.deadline
        deadline_datetime = datetime.combine(c_time.date(), deadline_time, tzinfo=c_time.tzinfo)
    else:
        deadline_datetime = None

    if deadline_datetime is None:
        status = 'Deadline not set'
    elif c_time <= deadline_datetime:
        status = 'Early'
    else:
        status = 'Late'

    # Check if the user has already clocked in and out on the same day
    start_of_day = datetime.combine(current_time.date(), datetime.min.time(), tzinfo=current_time.tzinfo)
    end_of_day = datetime.combine(current_time.date(), datetime.max.time(), tzinfo=current_time.tzinfo)
    existing_attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.location_id == location.id,
        Attendance.clock_in_time >= start_of_day,
        Attendance.clock_in_time <= end_of_day
    ).all()

    if existing_attendance and not any(a.is_clocked_in for a in existing_attendance):
        flash('You have already clocked in and out today. you are not allowed to clock in again today!!!.', 'danger')
        return redirect(url_for('attend.clock_in'))

    # Process clock-in or clock-out
    attendance = Attendance.query.filter_by(user_id=current_user.id, location_id=location.id, is_clocked_in=True).first()
    if attendance:
        attendance.clock_out_time = current_time
        attendance.is_clocked_in = False
        flash(f'Successfully clocked out at {current_time.strftime("%I:%M:%S %p %Z")}. Goodbye!!!', 'success')
    else:
        new_attendance = Attendance(
            user_id=current_user.id,
            location_id=location.id,
            clock_in_time=current_time,
            is_clocked_in=True,
            status=status
        )
        db.session.add(new_attendance)
        flash(f'Clock-in successful. Welcome, you arrived {status} at {current_time.strftime("%I:%M:%S %p %Z")} .', 'success')
    db.session.commit()

    return redirect(url_for('dash.dashboard'))

@attend.route('/attendance_matrix', methods=['GET'])
@login_required
def attendance_matrix():
    # Get the user's organization to check if they are an admin
    user_id = current_user.id
    organization = Organization.query.filter_by(user_id=user_id).first_or_404()

    # Ensure only admins can access this page
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0

    if not is_admin:
        flash('Unauthorized access. Only admins can view this page.', 'danger')
        return redirect(url_for('dash.dashboard'))

    # Get the selected location if provided
    selected_location_id = request.args.get('location_id')

    # Query for members of the organization
    members_query = User.query.join(Organization).filter(Organization.id == organization.id)

    # Filter by location if selected
    if selected_location_id:
        location = Location.query.get_or_404(selected_location_id)
        members_query = members_query.join(Location).filter(Location.id == selected_location_id)
    
    members = members_query.all()

    # Initialize matrix data
    matrix_data = []

    for member in members:
        # Query for all attendance records for the member
        attendance_query = Attendance.query.filter(Attendance.user_id == member.id, Attendance.location.has(organization_id=organization.id))
        
        # Filter by location if selected
        if selected_location_id:
            attendance_query = attendance_query.filter(Attendance.location_id == selected_location_id)
        
        attendance_records = attendance_query.all()

        # Calculate early and late arrivals
        early_count = sum(1 for record in attendance_records if record.status == 'Early')
        late_count = sum(1 for record in attendance_records if record.status == 'Late')

        # Append member's matrix data
        matrix_data.append({
            'member': member,
            'early_count': early_count,
            'late_count': late_count
        })

    # Get all locations to allow filtering
    locations = Location.query.filter_by(organization_id=organization.id).all()

    # Render the matrix view
    return render_template(
        'matrix.html',
        organization=organization,
        members=matrix_data,
        locations=locations,
        selected_location_id=selected_location_id,
        name=current_user.username,
        is_admin=is_admin,
        
    )


@attend.route('/attendance_log', methods=['GET', 'POST'])
@login_required
def attendance_log():
    organizations = Organization.query.filter_by(user_id=current_user.id).all()
    selected_org_id = request.args.get('organization_id')
    selected_location_id = request.args.get('location_id')
    selected_status = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    download = request.args.get('download')

    # Build the query based on filters
    query = Attendance.query.join(Location)

    if selected_org_id:
        query = query.filter(Location.organization_id == selected_org_id)

    if selected_location_id:
        query = query.filter(Attendance.location_id == selected_location_id)

    if selected_status:
        query = query.filter(Attendance.status == selected_status)

    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Attendance.clock_in_time >= start_date_obj)

    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(Attendance.clock_in_time <= end_date_obj)

    # Sort by clock_in_time descending
    query = query.order_by(Attendance.clock_in_time.desc())
    
    attendances = query.all()

    # Get user's current timezone
    user_timezone = current_user.timezone
    if user_timezone:
        user_tz = pytz.timezone(user_timezone)
    else:
        user_tz = pytz.utc

    current_time = datetime.now(user_tz)

    if not selected_org_id and not selected_location_id:
        # No organization selected, so no attendance records to display
        user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
        is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
        user_locations = current_user.locations
        return render_template('attendance_log.html',
                               organizations=organizations,
                               selected_org_id=selected_org_id,
                               selected_location_id=selected_location_id,
                               attendances=attendances,
                               name=current_user.username,
                               timezone=user_timezone,
                               current_date=current_time.strftime('%d-%m-%Y'),
                               current_time=current_time.strftime('%I:%M:%S %p %Z'),
                               is_admin=is_admin,
                               is_member=user_locations)

    # Convert attendance times to user's local timezone
    if attendances:
        for attendance in attendances:
            attendance.clock_in_time = attendance.clock_in_time.astimezone(user_tz)
            if attendance.clock_out_time:
                attendance.clock_out_time = attendance.clock_out_time.astimezone(user_tz)

    if download == 'pdf':
        html = render_template('attendance_pdf.html', attendances=attendances, user_timezone=current_user.timezone)
        pdf = pdfkit.from_string(html, False)
        response = BytesIO(pdf)
        response.seek(0)
        return send_file(response, mimetype='application/pdf', as_attachment=True, download_name='attendance.pdf')

    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations

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
        timezone=user_timezone,
        is_admin=is_admin,
        is_member=user_locations
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



@attend.route('/set_timezone', methods=['GET', 'POST'])
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

        return redirect(url_for('dash.dashboard'))

    # Get user's current timezone
    user_timezone = current_user.timezone

    user_id = current_user.id  # Static for demonstration; use authenticated user's ID in production
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations
    return render_template(
        'settings.html',
        timezones=TIMEZONES,
        user_timezone=user_timezone,
        name=current_user.username,
        is_admin=is_admin,
        is_member=user_locations
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
