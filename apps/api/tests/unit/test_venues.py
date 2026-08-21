"""Pure unit tests for the trusted CCFDDL iCalendar adapter."""

from datetime import UTC, datetime, timedelta

from researchos.venues.schemas import VenueDeadline
from researchos.venues.service import _parse_calendar, _select_relevant_items


def test_parse_calendar_unfolds_fields_and_preserves_timezone() -> None:
    raw = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:neurips-test
DTSTART:20261201T120000Z
DTEND:20261201T130000Z
SUMMARY:NeurIPS Test Deadline
DESCRIPTION:Paper deadline\\nCheck official website
LOCATION:UTC
URL:https://example.test/deadline
END:VEVENT
END:VCALENDAR
"""
    items = _parse_calendar(raw)
    assert len(items) == 1
    item = items[0]
    assert item.uid == "neurips-test"
    assert item.title == "NeurIPS Test Deadline"
    assert item.starts_at.tzinfo == UTC
    assert item.description == "Paper deadline\nCheck official website"
    assert item.url == "https://example.test/deadline"


def test_parse_calendar_handles_colon_in_quoted_fixed_offset_timezone() -> None:
    raw = '''BEGIN:VCALENDAR
BEGIN:VEVENT
UID:quoted-offset
DTSTART;TZID="UTC-12:00":20261201T120000
SUMMARY:Quoted offset deadline
END:VEVENT
END:VCALENDAR
'''
    items = _parse_calendar(raw)
    assert len(items) == 1
    assert items[0].starts_at.utcoffset() == -timedelta(hours=12)
    assert items[0].starts_at.hour == 12


def test_parse_calendar_falls_back_to_utc_for_invalid_quoted_timezone() -> None:
    raw = '''BEGIN:VCALENDAR
BEGIN:VEVENT
UID:invalid-timezone
DTSTART;TZID="Not/A Real:Zone":20261201T120000
SUMMARY:Invalid timezone deadline
END:VEVENT
END:VCALENDAR
'''
    items = _parse_calendar(raw)
    assert len(items) == 1
    assert items[0].starts_at.tzinfo == UTC


def test_select_relevant_items_prioritizes_upcoming_and_keeps_recent_history() -> None:
    def deadline(uid: str, year: int) -> VenueDeadline:
        return VenueDeadline(
            uid=uid,
            title=uid,
            starts_at=datetime(year, 1, 1, tzinfo=UTC),
        )

    selected = _select_relevant_items(
        [
            deadline("oldest", 2020),
            deadline("recent", 2025),
            deadline("next", 2027),
            deadline("later", 2028),
        ],
        now=datetime(2026, 1, 1, tzinfo=UTC),
        limit=3,
    )

    assert [item.uid for item in selected] == ["recent", "next", "later"]


def test_parse_calendar_skips_incomplete_events() -> None:
    raw = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:no-summary
DTSTART:20261201T120000Z
END:VEVENT
BEGIN:VEVENT
UID:no-date
SUMMARY:Missing date
END:VEVENT
END:VCALENDAR
"""
    assert _parse_calendar(raw) == []
