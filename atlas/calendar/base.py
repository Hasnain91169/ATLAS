from abc import ABC, abstractmethod
from datetime import date, tzinfo

from atlas.models.calendar import CalendarEvent


class CalendarAdapter(ABC):
    @abstractmethod
    def fetch_events(self, day: date, tz: tzinfo) -> list[CalendarEvent]:
        raise NotImplementedError
