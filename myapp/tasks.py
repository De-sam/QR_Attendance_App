from myapp.celery import celery
from myapp import create_app
from myapp.models import db, Attendance, Location
from datetime import datetime, timedelta
import pytz

app = create_app()

@celery.task(name='myapp.tasks.auto_clock_out')
def auto_clock_out():
    with app.app_context():
        locations = Location.query.filter(Location.closing_time.isnot(None)).all()
        for location in locations:
            # Iterate over members associated with the location
            for member in location.members:
                # Get the user's timezone
                user_timezone = member.timezone if member.timezone else 'UTC'
                tz = pytz.timezone(user_timezone)
                current_time = datetime.now(tz)
                auto_clock_out_time = datetime.combine(current_time.date(), location.closing_time, tzinfo=tz) + timedelta(minutes=30)

                open_attendances = Attendance.query.filter(
                    Attendance.location_id == location.id,
                    Attendance.user_id == member.id,
                    Attendance.is_clocked_in == True,
                    Attendance.clock_in_time <= auto_clock_out_time
                ).all()

                for attendance in open_attendances:
                    attendance.clock_out_time = auto_clock_out_time
                    attendance.is_clocked_in = False

        db.session.commit()
