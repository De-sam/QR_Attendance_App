from .celery import celery
from .models import db, Attendance, Location
from datetime import datetime, timedelta
import pytz

@celery.task
def auto_clock_out():
    # Get all locations with a closing time set
    locations = Location.query.filter(Location.closing_time.isnot(None)).all()
    for location in locations:
        tz = pytz.timezone(location.organization.user.timezone if location.organization.user.timezone else 'UTC')
        current_time = datetime.now(tz)
        auto_clock_out_time = datetime.combine(current_time.date(), location.closing_time, tzinfo=tz) + timedelta(minutes=30)

        # Check for open attendance records past auto clock-out time
        open_attendances = Attendance.query.filter(
            Attendance.location_id == location.id,
            Attendance.is_clocked_in == True,
            Attendance.clock_in_time <= auto_clock_out_time
        ).all()

        for attendance in open_attendances:
            attendance.clock_out_time = auto_clock_out_time
            attendance.is_clocked_in = False

    db.session.commit()
