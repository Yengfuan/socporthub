from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.config import get_settings
from api.database import get_db
from api.models import CalendarEvent, Committee, User, UserRole
from api.schemas import CalendarEventCreate, CalendarEventOut, CalendarFeedUrlOut

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/feed-url", response_model=CalendarFeedUrlOut)
def get_feed_url(request: Request, _user: User = Depends(get_current_user)) -> CalendarFeedUrlOut:
    """Hands the authenticated user the subscribe URL (with token) for their own
    calendar app — keeps the token out of frontend source, only given to approved users."""
    settings = get_settings()
    base = str(request.base_url).rstrip("/")
    url = f"{base}/api/calendar/feed.ics"
    if settings.calendar_feed_token:
        url += f"?token={settings.calendar_feed_token}"
    return CalendarFeedUrlOut(url=url)


def _to_out(e: CalendarEvent) -> CalendarEventOut:
    return CalendarEventOut(
        id=e.id,
        title=e.title,
        description=e.description,
        date=e.event_date.isoformat(),
        committee_id=e.committee_id,
        committee_name=e.committee.name,
        committee_color=e.committee.color,
    )


@router.get("", response_model=list[CalendarEventOut])
def get_events(
    start: date | None = None,
    end: date | None = None,
    committee_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CalendarEventOut]:
    today = date.today()
    time_min = start or (today.replace(day=1) - timedelta(days=31))
    time_max = end or (today.replace(day=1) + timedelta(days=62))

    query = db.query(CalendarEvent).filter(
        CalendarEvent.event_date >= time_min, CalendarEvent.event_date <= time_max
    )
    if committee_id is not None:
        query = query.filter(CalendarEvent.committee_id == committee_id)

    return [_to_out(e) for e in query.order_by(CalendarEvent.event_date).all()]


@router.post("", response_model=CalendarEventOut, status_code=status.HTTP_201_CREATED)
def add_event(
    req: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarEventOut:
    if user.role == UserRole.admin:
        if req.committee_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "committee_id is required for admin-created events")
        committee_id = req.committee_id
    else:
        if not user.committee_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are not assigned to a committee yet")
        committee_id = req.committee_id if req.committee_id in user.committee_ids else sorted(user.committee_ids)[0]

    committee = db.get(Committee, committee_id)
    if not committee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Committee not found")

    event = CalendarEvent(
        committee_id=committee.id,
        created_by=user.id,
        title=req.title,
        description=req.description,
        event_date=req.date,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _to_out(event)


def _escape_ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


@router.get("/feed.ics")
def calendar_feed(token: str | None = None, db: Session = Depends(get_db)) -> Response:
    """Public iCalendar feed for subscribing from Google/Apple/Outlook calendar apps.

    No Telegram auth here — calendar apps can't send our custom header — so this is
    protected only by an optional shared token in the URL, same trust model as Google
    Calendar's own "secret address in iCal format" feature.
    """
    settings = get_settings()
    if settings.calendar_feed_token and token != settings.calendar_feed_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or missing feed token")

    events = db.query(CalendarEvent).order_by(CalendarEvent.event_date).all()

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Social Port Hub//EN", "CALSCALE:GREGORIAN"]
    now_stamp = date.today().strftime("%Y%m%dT000000Z")
    for e in events:
        start_str = e.event_date.strftime("%Y%m%d")
        end_str = (e.event_date + timedelta(days=1)).strftime("%Y%m%d")
        summary = _escape_ics_text(f"[{e.committee.name}] {e.title}")
        lines += ["BEGIN:VEVENT", f"UID:{e.id}@socporthub", f"DTSTAMP:{now_stamp}"]
        lines += [f"DTSTART;VALUE=DATE:{start_str}", f"DTEND;VALUE=DATE:{end_str}", f"SUMMARY:{summary}"]
        if e.description:
            lines.append(f"DESCRIPTION:{_escape_ics_text(e.description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    return Response(content="\r\n".join(lines), media_type="text/calendar")
