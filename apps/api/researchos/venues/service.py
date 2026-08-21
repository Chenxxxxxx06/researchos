"""Read-only CCFDDL iCalendar adapter.

The URL is deliberately fixed. User input never becomes an outbound URL, which
keeps this endpoint from becoming an SSRF proxy.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from researchos.common.errors import DependencyError

from .schemas import VenueDeadline, VenueDeadlineFeed

CCFDDL_ICAL_URL = "https://ccfddl.com/conference/deadlines_zh.ics"
_DATE_FORMATS = ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d")
_MAX_FEED_ITEMS = 500


class VenueDeadlineService:
    async def fetch(self) -> VenueDeadlineFeed:
        try:
            async with httpx.AsyncClient(
                timeout=12,
                follow_redirects=True,
                headers={"User-Agent": "ResearchOS/venue-deadlines"},
            ) as client:
                response = await client.get(CCFDDL_ICAL_URL)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DependencyError("CCFDDL deadline feed is temporarily unavailable.") from exc

        fetched_at = datetime.now(UTC)
        items = _select_relevant_items(
            _parse_calendar(response.text),
            now=fetched_at,
            limit=_MAX_FEED_ITEMS,
        )
        return VenueDeadlineFeed(
            source_name="ccfddl/ccf-deadlines",
            source_url=CCFDDL_ICAL_URL,
            fetched_at=fetched_at,
            items=items,
        )


def _select_relevant_items(
    items: list[VenueDeadline],
    *,
    now: datetime,
    limit: int,
) -> list[VenueDeadline]:
    """Keep upcoming deadlines and fill remaining capacity with recent history."""
    if limit <= 0:
        return []
    ordered = sorted(items, key=lambda item: item.starts_at)
    upcoming = [item for item in ordered if item.starts_at >= now]
    if len(upcoming) >= limit:
        return upcoming[:limit]
    history = [item for item in ordered if item.starts_at < now]
    return history[-(limit - len(upcoming)) :] + upcoming


def _parse_calendar(raw: str) -> list[VenueDeadline]:
    lines: list[str] = []
    for source_line in raw.replace("\r\n", "\n").split("\n"):
        if source_line.startswith((" ", "\t")) and lines:
            lines[-1] += source_line[1:]
        else:
            lines.append(source_line)

    events: list[VenueDeadline] = []
    current: dict[str, tuple[str, str]] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                event = _event_from_fields(current)
                if event is not None:
                    events.append(event)
            current = None
            continue
        if current is None:
            continue
        content_line = _split_content_line(line)
        if content_line is None:
            continue
        key_part, value = content_line
        key, _, params = key_part.partition(";")
        current[key.upper()] = (params, _unescape(value))
    return events


def _event_from_fields(fields: dict[str, tuple[str, str]]) -> VenueDeadline | None:
    title = fields.get("SUMMARY", ("", ""))[1].strip()
    start_field = fields.get("DTSTART")
    if not title or start_field is None:
        return None
    starts_at = _parse_datetime(*start_field)
    if starts_at is None:
        return None
    end_field = fields.get("DTEND")
    ends_at = _parse_datetime(*end_field) if end_field else None
    uid = fields.get("UID", ("", ""))[1] or f"{title}-{starts_at.isoformat()}"
    return VenueDeadline(
        uid=uid[:500],
        title=title[:500],
        description=(fields.get("DESCRIPTION", ("", ""))[1] or None),
        location=(fields.get("LOCATION", ("", ""))[1] or None),
        starts_at=starts_at,
        ends_at=ends_at,
        url=(fields.get("URL", ("", ""))[1] or None),
    )


def _split_content_line(line: str) -> tuple[str, str] | None:
    """Split an iCalendar content line at the first colon outside quotes."""
    quoted = False
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if character == ":" and not quoted:
            return line[:index], line[index + 1 :]
    return None


def _parse_datetime(params: str, value: str) -> datetime | None:
    parsed_timezone: tzinfo = UTC
    match = re.search(r'(?:^|;)TZID=(?:"([^"]+)"|([^;]+))', params)
    if match:
        timezone_name = (match.group(1) or match.group(2)).strip()
        offset_match = re.fullmatch(
            r"(?:UTC|GMT)([+-])(\d{1,2})(?::?(\d{2}))?",
            timezone_name,
            re.IGNORECASE,
        )
        if offset_match:
            hours = int(offset_match.group(2))
            minutes = int(offset_match.group(3) or 0)
            offset = timedelta(hours=hours, minutes=minutes)
            if offset_match.group(1) == "-":
                offset = -offset
            try:
                parsed_timezone = timezone(offset, name=timezone_name.upper())
            except ValueError:
                parsed_timezone = UTC
        else:
            try:
                parsed_timezone = ZoneInfo(timezone_name)
            except (ZoneInfoNotFoundError, OSError, ValueError):
                parsed_timezone = UTC
    for date_format in _DATE_FORMATS:
        try:
            result = datetime.strptime(value, date_format)
            if date_format.endswith("Z"):
                return result.replace(tzinfo=UTC)
            return result.replace(tzinfo=parsed_timezone)
        except ValueError:
            continue
    return None


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )
