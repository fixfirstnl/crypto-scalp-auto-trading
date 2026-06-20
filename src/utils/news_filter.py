"""Economic news filter for high-impact event detection."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional

import aiohttp

logger = logging.getLogger(__name__)

HIGH_IMPACT_KEYWORDS = [
    "NFP", "Non-Farm Payrolls", "CPI", "FOMC", "Fed", "Interest Rate",
    "Jackson Hole", "ECB", "BOE", "BOJ", "GDP", "Unemployment",
    "ETF Approval", "Bitcoin ETF", "Ethereum ETF", "Regulation",
    "SEC", "CFTC", "Binance", "Coinbase", "Hack", "Halving",
    "Merge", "Shapella", "Dencun", "FOMC Statement", "Powell",
    "Nonfarm", "Retail Sales", "PPI", "Core CPI", "Core PCE",
]


class NewsFilter:
    """Filter and detect high-impact economic news events.

    Uses in-memory caching with configurable refresh intervals.
    Supports ForexFactory scraping and fallback to manual event lists.
    """

    def __init__(
        self,
        calendar_source: str = "forexfactory",
        refresh_interval_minutes: int = 30,
    ) -> None:
        """Initialize the news filter.

        Args:
            calendar_source: Source for economic calendar (forexfactory, api, manual).
            refresh_interval_minutes: How often to refresh the calendar cache.
        """
        self.calendar_source = calendar_source
        self.refresh_interval = timedelta(minutes=refresh_interval_minutes)
        self._cache: List[Dict] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_lock = asyncio.Lock()

    async def _fetch_forexfactory(self, days: int = 7) -> List[Dict]:
        """Scrape ForexFactory economic calendar (placeholder implementation).

        In production, replace with actual scraping or API integration.
        """
        logger.warning("ForexFactory scraping not implemented; using manual events")
        return await self._fetch_manual_events(days)

    async def _fetch_manual_events(self, days: int = 7) -> List[Dict]:
        """Return manually configured high-impact events as fallback."""
        now = datetime.now(timezone.utc)
        events = []
        # Example: generate placeholder events for the next N days
        # In production, this could read from a configuration file or API
        for i in range(days):
            day = now + timedelta(days=i)
            # Placeholder: NFP is typically first Friday
            if day.weekday() == 4 and 1 <= day.day <= 7:  # First Friday
                events.append({
                    "title": "Non-Farm Payrolls (NFP)",
                    "time": day.replace(hour=12, minute=30),
                    "impact": "high",
                    "currency": "USD",
                })
            # Placeholder: FOMC typically every 6 weeks
            if day.weekday() == 2 and day.day in [17, 18]:  # Random placeholder
                events.append({
                    "title": "FOMC Interest Rate Decision",
                    "time": day.replace(hour=18, minute=0),
                    "impact": "high",
                    "currency": "USD",
                })
        return events

    async def fetch_economic_calendar(self, days: int = 7) -> List[Dict]:
        """Fetch economic calendar events with caching.

        Args:
            days: Number of days ahead to fetch.

        Returns:
            List of event dictionaries with title, time, impact, currency.
        """
        async with self._cache_lock:
            if self._cache and self._last_fetch:
                if datetime.now(timezone.utc) - self._last_fetch < self.refresh_interval:
                    return self._cache

            try:
                if self.calendar_source == "forexfactory":
                    events = await self._fetch_forexfactory(days)
                elif self.calendar_source == "api":
                    events = await self._fetch_api_calendar(days)
                else:
                    events = await self._fetch_manual_events(days)

                self._cache = events
                self._last_fetch = datetime.now(timezone.utc)
                logger.info(f"Fetched {len(events)} economic events")
                return events
            except Exception as e:
                logger.error(f"Failed to fetch economic calendar: {e}")
                return self._cache if self._cache else []

    async def _fetch_api_calendar(self, days: int = 7) -> List[Dict]:
        """Fetch from a hypothetical API endpoint (placeholder)."""
        # In production, replace with a real economic calendar API
        logger.warning("API calendar source not configured; using manual events")
        return await self._fetch_manual_events(days)

    def _is_high_impact(self, event: Dict) -> bool:
        """Check if an event is high-impact based on keywords or impact field."""
        impact = event.get("impact", "").lower()
        if impact in ("high", "red", "3"):
            return True
        title = event.get("title", "").upper()
        return any(kw.upper() in title for kw in HIGH_IMPACT_KEYWORDS)

    def is_high_impact_news_within(self, minutes: int = 15) -> bool:
        """Check if any high-impact news event is within ±X minutes.

        Args:
            minutes: Window around current time to check.

        Returns:
            True if a high-impact event is within the window.
        """
        if not self._cache:
            return False
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=minutes)
        for event in self._cache:
            if not self._is_high_impact(event):
                continue
            event_time = event.get("time")
            if not isinstance(event_time, datetime):
                continue
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            if abs(event_time - now) <= window:
                return True
        return False

    def get_upcoming_events(self, hours: int = 2) -> List[Dict]:
        """Get upcoming high-impact events within the next N hours.

        Args:
            hours: Lookahead window in hours.

        Returns:
            List of upcoming high-impact event dictionaries.
        """
        if not self._cache:
            return []
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        upcoming = []
        for event in self._cache:
            if not self._is_high_impact(event):
                continue
            event_time = event.get("time")
            if not isinstance(event_time, datetime):
                continue
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            if now <= event_time <= cutoff:
                upcoming.append(event)
        return sorted(upcoming, key=lambda e: e["time"])

    def should_block_trading(self, buffer_minutes: int = 15) -> Tuple[bool, str]:
        """Determine if trading should be blocked due to upcoming news.

        Args:
            buffer_minutes: Minutes before/after news to block trading.

        Returns:
            Tuple of (should_block, reason).
        """
        if self.is_high_impact_news_within(buffer_minutes):
            upcoming = self.get_upcoming_events(hours=2)
            if upcoming:
                event = upcoming[0]
                reason = (
                    f"High-impact news: {event.get('title', 'Unknown')} "
                    f"at {event.get('time', 'Unknown')}"
                )
                return True, reason
            return True, "High-impact news within buffer window"
        return False, ""
