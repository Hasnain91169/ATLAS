from datetime import date, datetime, time, tzinfo

from atlas.calendar.base import CalendarAdapter
from atlas.models.calendar import CalendarEvent


class StubCalendarAdapter(CalendarAdapter):
    def fetch_events(self, day: date, tz: tzinfo) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                title="Daily standup",
                start=datetime.combine(day, time(9, 30), tzinfo=tz),
                end=datetime.combine(day, time(10, 0), tzinfo=tz),
            ),
            CalendarEvent(
                title="Project sync",
                start=datetime.combine(day, time(13, 0), tzinfo=tz),
                end=datetime.combine(day, time(14, 0), tzinfo=tz),
            ),
            CalendarEvent(
                title="1:1 check-in",
                start=datetime.combine(day, time(15, 30), tzinfo=tz),
                end=datetime.combine(day, time(16, 0), tzinfo=tz),
            ),
        ]
