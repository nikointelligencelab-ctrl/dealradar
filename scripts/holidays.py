"""
US retail holiday calendar.

Deal traffic is seasonal and the season is knowable years ahead. This module
computes the windows so the site can promote the right event without anyone
editing a date by hand.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, asdict
from datetime import date, timedelta


@dataclass
class Window:
    slug: str
    name: str
    start: date
    end: date
    peak: date

    def is_live(self, today: date) -> bool:
        return self.start <= today <= self.end

    def days_until(self, today: date) -> int:
        return (self.peak - today).days

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("start", "end", "peak"):
            d[k] = d[k].isoformat()
        return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th weekday of a month. weekday: Mon=0 .. Sun=6."""
    days = [
        d for d in calendar.Calendar().itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[n - 1]


def thanksgiving(year: int) -> date:
    """Fourth Thursday in November."""
    return _nth_weekday(year, 11, 3, 4)


def black_friday(year: int) -> date:
    return thanksgiving(year) + timedelta(days=1)


def cyber_monday(year: int) -> date:
    return thanksgiving(year) + timedelta(days=4)


def build_calendar(year: int) -> list[Window]:
    """
    Windows are deliberately wider than the day itself — retailers now start
    'Black Friday' pricing in early November, and the feed should reflect what
    shoppers are actually seeing.
    """
    bf = black_friday(year)
    cm = cyber_monday(year)

    return [
        Window("new-year", "New Year Sales",
               date(year, 1, 1), date(year, 1, 15), date(year, 1, 1)),
        Window("presidents-day", "Presidents Day",
               _nth_weekday(year, 2, 0, 3) - timedelta(days=5),
               _nth_weekday(year, 2, 0, 3) + timedelta(days=1),
               _nth_weekday(year, 2, 0, 3)),
        Window("memorial-day", "Memorial Day",
               _nth_weekday(year, 5, 0, 4) - timedelta(days=96 % 90),
               _nth_weekday(year, 5, 0, 4) + timedelta(days=1),
               _nth_weekday(year, 5, 0, 4)),
        Window("july-4", "Fourth of July",
               date(year, 6, 28), date(year, 7, 6), date(year, 7, 4)),
        Window("back-to-school", "Back to School",
               date(year, 7, 15), date(year, 9, 5), date(year, 8, 15)),
        Window("labor-day", "Labor Day",
               _nth_weekday(year, 9, 0, 1) - timedelta(days=5),
               _nth_weekday(year, 9, 0, 1) + timedelta(days=1),
               _nth_weekday(year, 9, 0, 1)),
        Window("halloween", "Halloween",
               date(year, 10, 1), date(year, 10, 31), date(year, 10, 31)),
        Window("black-friday", "Black Friday",
               date(year, 11, 1), bf + timedelta(days=1), bf),
        Window("cyber-monday", "Cyber Monday",
               bf + timedelta(days=2), cm + timedelta(days=1), cm),
        Window("december", "Holiday Shopping",
               date(year, 12, 1), date(year, 12, 24), date(year, 12, 15)),
    ]


def current_window(today: date | None = None) -> Window | None:
    """The live event, if any. Later windows win when two overlap."""
    today = today or date.today()
    live = [w for w in build_calendar(today.year) if w.is_live(today)]
    return max(live, key=lambda w: w.peak) if live else None


def next_window(today: date | None = None) -> Window:
    """The next peak coming up, rolling into next year if needed."""
    today = today or date.today()
    upcoming = [w for w in build_calendar(today.year) if w.peak >= today]
    if not upcoming:
        upcoming = build_calendar(today.year + 1)
    return min(upcoming, key=lambda w: w.peak)


if __name__ == "__main__":
    t = date.today()
    print(f"today: {t}")
    cur = current_window(t)
    print(f"live now: {cur.name if cur else 'none'}")
    nxt = next_window(t)
    print(f"next peak: {nxt.name} on {nxt.peak} ({nxt.days_until(t)} days)")
