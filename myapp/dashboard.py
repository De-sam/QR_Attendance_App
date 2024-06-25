from flask import Blueprint,render_template,session,send_file,Response
from flask_login import login_required,current_user
import uuid
from flask import current_app
from myapp import render_template,request,flash,redirect,url_for
from . import db
from .models import User,Organization,Location,QRCode,JoinRequest,Attendance
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from haversine import haversine, Unit
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone,date
import pytz

dash= Blueprint("dash", __name__)


@dash.route('/dashboard/')
@login_required
def dashboard():
    user_id = current_user.id
    search_query = request.args.get('search', '').strip()
    user = current_user

    # Determine if the user is an admin
    is_admin = Organization.query.with_entities(func.count(Organization.id)).filter_by(user_id=user_id).scalar() > 0
    user_locations = current_user.locations

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

    user_timezone = current_user.timezone
    if user_timezone:
        user_tz = pytz.timezone(user_timezone)
        current_time = datetime.now(user_tz)
    else:
        user_tz = pytz.utc
        current_time = datetime.now(pytz.utc)

    # Get the current date in the user's timezone
    today = current_time.date()
    five_days_ago = today - timedelta(days=5)

    # Query to get today's attendance records for the current user
    today_attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        db.func.date(Attendance.clock_in_time) == today
    ).all()

    # Convert attendance times to user's timezone
    for record in today_attendance:
        record.clock_in_time = record.clock_in_time.astimezone(user_tz)
        if record.clock_out_time:
            record.clock_out_time = record.clock_out_time.astimezone(user_tz)

    total_members = len(member_details)
    total_present = sum(1 for record in today_attendance if record.is_clocked_in or record.clock_out_time is not None)
    total_absent = total_members - total_present

    # Query to get attendance records for the current user for the last five days, sorted by clock_in_time descending
    last_five_days_attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        db.func.date(db.func.timezone(user_timezone, Attendance.clock_in_time)) >= five_days_ago,
        db.func.date(db.func.timezone(user_timezone, Attendance.clock_in_time)) <= today
    ).order_by(Attendance.clock_in_time.desc()).all()

    # Convert attendance times to user's timezone for past records
    for record in last_five_days_attendance:
        record.clock_in_time = record.clock_in_time.astimezone(user_tz)
        if record.clock_out_time:
            record.clock_out_time = record.clock_out_time.astimezone(user_tz)

    # Query to get attendance records for the current user for the current month
    first_day_of_month = today.replace(day=1)
    month_attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        db.func.date(db.func.timezone(user_timezone, Attendance.clock_in_time)) >= first_day_of_month,
        db.func.date(db.func.timezone(user_timezone, Attendance.clock_in_time)) <= today
    ).order_by(Attendance.clock_in_time.desc()).all()

    # Convert attendance times to user's timezone for month records
    for record in month_attendance_records:
        record.clock_in_time = record.clock_in_time.astimezone(user_tz)
        if record.clock_out_time:
            record.clock_out_time = record.clock_out_time.astimezone(user_tz)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.clock_in_time >= today_start,
        Attendance.clock_in_time < today_end
    ).order_by(Attendance.clock_in_time.desc()).first()

    if attendance and not attendance.clock_out_time:
        action = "Clock Out"
    else:
        action = "Clock In"

    url = url_for('attend.clock_in')

    # Prepare calendar_data for the current month
    calendar_data = {}
    for attendance_record in month_attendance_records:
        # Format the date to match FullCalendar's expected format (YYYY-MM-DD)
        date = attendance_record.clock_in_time.strftime('%Y-%m-%d')

        # Determine the color based on lateness or earliness
        color = 'red' if attendance_record.status == 'Late' else 'green'

        # Check if an event for this date already exists
        if date not in calendar_data:
            # Add the event for this date
            status = "Late" if attendance_record.status == "Late" else "Early"
            title = f"{status} | {attendance_record.clock_in_time.strftime('%I:%M %p')}"
            calendar_data[date] = {
                'title': title,
                'start': date,
                'backgroundColor': color
            }

    import json
    return render_template(
        'dashboard_base.html',
        calendar_data=json.dumps(list(calendar_data.values())),
        timezone=user_timezone,
        current_date=current_time.strftime('%d-%m-%Y'),
        current_time=current_time.strftime('%I:%M:%S %p %Z'),
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
        is_member=user_locations,
        action=action,
        url=url,
        user_attendance_records=last_five_days_attendance  # Only the last 5 days for another purpose
    )
