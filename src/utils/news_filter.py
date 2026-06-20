"""NewsFilter: Economic news event filtering for trading avoidance.

Filters high-impact economic events that could cause volatile price movements:
- NFP (Non-Farm Payrolls)
- CPI (Consumer Price Index)
- FOMC (Federal Reserve meetings)
- ECB meetings
- Major earnings announcements

Provides a configurable buffer time (default 15 minutes) before and after
events during which trading is blocked.

Usage:
    news = NewsFilter(news_buffer_minutes=15)
    await news.fetch_economic_calendar(days=7)
    
    should_block, reason = news.should_block_trading()
    if should_block:
        print(f"Trading blocked: {reason}")
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)


class NewsFilter:
    """Economic news filter with configurable buffer time.
    
    Parameters
    ----------
    news_buffer_minutes : int, default 15
        Minutes before and after a high-impact event to block trading.
    """

    # High-impact events that trigger trading blocks
    HIGH_IMPACT_EVENTS = [
        'nfp', 'non-farm payrolls', 'nonfarm payrolls',
        'cpi', 'consumer price index',
        'fomc', 'federal reserve', 'fed interest rate',
        'ecb', 'european central bank',
        'gdp', 'gross domestic product',
        'unemployment rate',
        'retail sales',
        'ppi', 'producer price index',
        'pmis', 'ism',
    ]

    def __init__(self, news_buffer_minutes: int = 15) -> None:
        self.news_buffer_minutes = news_buffer_minutes
        self.economic_calendar: List[Dict[str, Any]] = []
        self._last_fetch: Optional[datetime] = None
        
        logger.info("NewsFilter initialized | buffer=%d min", news_buffer_minutes)

    async def fetch_economic_calendar(self, days: int = 7) -> None:
        """Fetch economic calendar from external source.
        
        Parameters
        ----------
        days : int, default 7
            Number of days to fetch.
        
        Note
        ----
        In production, this would fetch from a real economic calendar API
        (e.g., ForexFactory, Investing.com, or Myfxbook). For now, we use
        a placeholder that can be replaced with actual API integration.
        """
        # Placeholder: In production, replace with actual API call
        # Example: fetch from ForexFactory or Myfxbook API
        
        # For now, generate a simple placeholder calendar
        # In production, this should be replaced with actual data fetching
        self.economic_calendar = []
        self._last_fetch = datetime.now(timezone.utc)
        
        logger.info("Economic calendar fetched | events=%d", len(self.economic_calendar))

    def add_event(self, event_time: datetime, event_name: str, impact: str = 'high') -> None:
        """Manually add an economic event.
        
        Parameters
        ----------
        event_time : datetime
            Event time in UTC.
        event_name : str
            Event name.
        impact : str, default 'high'
            Event impact level: 'high', 'medium', 'low'.
        """
        self.economic_calendar.append({
            'time': event_time,
            'name': event_name,
            'impact': impact,
        })
        logger.info("Event added: %s at %s", event_name, event_time.isoformat())

    def should_block_trading(self) -> Tuple[bool, str]:
        """Check if trading should be blocked due to upcoming or recent news.
        
        Returns
        -------
        tuple
            (should_block: bool, reason: str)
        """
        now = datetime.now(timezone.utc)
        buffer = timedelta(minutes=self.news_buffer_minutes)
        
        for event in self.economic_calendar:
            event_time = event.get('time')
            if not event_time:
                continue
            
            # Check if current time is within buffer of event
            if event_time - buffer <= now <= event_time + buffer:
                event_name = event.get('name', 'Unknown event')
                impact = event.get('impact', 'high')
                
                if impact == 'high' or self._is_high_impact(event_name):
                    reason = (
                        f"High-impact event: {event_name} "
                        f"at {event_time.strftime('%Y-%m-%d %H:%M UTC')} "
                        f"(buffer: ±{self.news_buffer_minutes} min)"
                    )
                    logger.warning("Trading blocked: %s", reason)
                    return True, reason
        
        return False, ""

    def _is_high_impact(self, event_name: str) -> bool:
        """Check if an event name indicates high impact."""
        event_lower = event_name.lower()
        return any(keyword in event_lower for keyword in self.HIGH_IMPACT_EVENTS)

    def get_upcoming_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get upcoming high-impact events.
        
        Parameters
        ----------
        hours : int, default 24
            Look ahead hours.
        
        Returns
        -------
        list
            Upcoming events within the specified window.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        
        upcoming = []
        for event in self.economic_calendar:
            event_time = event.get('time')
            if event_time and now <= event_time <= cutoff:
                if self._is_high_impact(event.get('name', '')):
                    upcoming.append(event)
        
        return upcoming

    def clear_events(self) -> None:
        """Clear all stored events."""
        self.economic_calendar = []
        logger.info("Economic calendar cleared")
