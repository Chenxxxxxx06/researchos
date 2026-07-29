"""Pure unit tests for the trusted CCFDDL iCalendar adapter."""

from datetime import UTC

from researchos.venues.service import _parse_calendar


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
