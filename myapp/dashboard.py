from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import pytz
import json
from .models import User,Organization,Location,QRCode,JoinRequest,Attendance

dash = Blueprint("dash", __name__)

@dash.route('/dashboard/')
@login_required
def dashboard():
    user_id = current_user.id
    search_query = request.args.get('search', '').strip().lower()
    user_timezone = current_user.timezone or 'UTC'
    user_tz = pytz.timezone(user_timezone)
    current_time = datetime.now(user_tz)
    today = current_time.date()
    five_days_ago = today - timedelta(days=5)
    first_day_of_month = today.replace(day=1)

    # Helper function for timezone conversion
    def convert_to_user_tz(dt):
        return dt.astimezone(user_tz) if dt else None

    # Queries
    organizations = Organization.query.options(
        joinedload(Organization.locations),
        joinedload(Organization.join_requests).joinedload(JoinRequest.location)
    ).filter_by(user_id=user_id).all()

    pending_join_requests = [request for org in organizations for request in org.join_requests if request.status == 'pending']
    
    member_details = [
        {
            'id': member.id,
            'name': member.username,
            'email': member.email,
            'alias': location.alias,
            'organization_name': org.name,
            'location_id': location.id
        }
        for org in organizations for location in org.locations for member in location.members
        if not search_query or search_query in member.username.lower()
    ]

    # Attendance Queries
    attendance_filters = Attendance.user_id == current_user.id
    today_attendance = Attendance.query.filter(
        attendance_filters,
        func.date(Attendance.clock_in_time) == today
    ).all()

    last_five_days_attendance = Attendance.query.filter(
        attendance_filters,
        func.date(func.timezone(user_timezone, Attendance.clock_in_time)) >= five_days_ago,
        func.date(func.timezone(user_timezone, Attendance.clock_in_time)) <= today
    ).order_by(Attendance.clock_in_time.desc()).all()

    month_attendance_records = Attendance.query.filter(
        attendance_filters,
        func.date(func.timezone(user_timezone, Attendance.clock_in_time)) >= first_day_of_month,
        func.date(func.timezone(user_timezone, Attendance.clock_in_time)) <= today
    ).order_by(Attendance.clock_in_time.desc()).all()

    # Convert attendance times to user's timezone
    for record in today_attendance + last_five_days_attendance + month_attendance_records:
        record.clock_in_time = convert_to_user_tz(record.clock_in_time)
        record.clock_out_time = convert_to_user_tz(record.clock_out_time)

    total_members = len(member_details)
    total_present = sum(1 for record in today_attendance if record.is_clocked_in or record.clock_out_time)
    total_absent = total_members - total_present

    # Determine clock action
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.clock_in_time >= today_start,
        Attendance.clock_in_time < today_end
    ).order_by(Attendance.clock_in_time.desc()).first()

    action = "Clock Out" if attendance and not attendance.clock_out_time else "Clock In"
    url = url_for('attend.clock_in')

    # Prepare calendar data
    calendar_data = {}
    for record in month_attendance_records:
        date_str = record.clock_in_time.strftime('%Y-%m-%d')
        color = 'red' if record.status == 'Late' else 'green'
        status = "Late" if record.status == "Late" else "Early"
        title = f"{status} | {record.clock_in_time.strftime('%I:%M %p')}"
        if date_str not in calendar_data:
            calendar_data[date_str] = {
                'title': title,
                'start': date_str,
                'backgroundColor': color
            }

    return render_template(
        'dashboard_base.html',
        calendar_data=json.dumps(list(calendar_data.values())),
        timezone=user_timezone,
        current_date=current_time.strftime('%d-%m-%Y'),
        current_time=current_time.strftime('%I:%M:%S %p %Z'),
        name=current_user.username,
        organization_count=len(organizations),
        location_count=sum(len(org.locations) for org in organizations),
        organizations=organizations,
        join_requests=pending_join_requests,
        member_details=member_details if member_details else None,
        location=Location,
        has_results=bool(member_details),
        total_present=total_present,
        total_absent=total_absent,
        is_admin=len(organizations) > 0,
        is_member=current_user.locations,
        action=action,
        url=url,
        user_attendance_records=last_five_days_attendance  # Only the last 5 days for another purpose
    )

