"""Baut einen persönlichen Podcast-RSS-Feed (RSS 2.0 + iTunes-Tags) aus den
gespeicherten Briefings eines Users. Wird über einen unguessable feed_token
öffentlich (ohne Login) ausgeliefert, der Token IST das Credential, liegt beim
User in seiner Podcast-/Alexa-App.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from ..briefing_models import UserBriefing


def _rfc2822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def build_feed(base_url: str, feed_token: str, briefings: list[UserBriefing]) -> str:
    """base_url = öffentliche News-Frontend-Basis (z. B. https://news.saganta.de)."""
    base = base_url.rstrip("/")
    self_url = f"{base}/briefing/feed/{feed_token}.xml"
    now = _rfc2822(datetime.now(timezone.utc))

    items_xml: list[str] = []
    for ub in briefings:
        if not ub.audio_path:
            continue  # nur Episoden mit Audio in den Podcast
        content = ub.content or {}
        top = content.get("top_story") or {}
        date_str = ub.briefing_date.isoformat()
        title = f"Briefing {ub.briefing_date.strftime('%d.%m.%Y')}"
        desc_lines = [top.get("title")] if top.get("title") else []
        for sec in content.get("sections", [])[:4]:
            heads = ", ".join(i["title"] for i in sec.get("items", [])[:2])
            if heads:
                desc_lines.append(f"{sec.get('label', '')}: {heads}")
        description = " · ".join(d for d in desc_lines if d) or "Dein tägliches Briefing."
        mime = ub.audio_mime or "audio/mpeg"
        audio_url = f"{base}/briefing/audio/{feed_token}/{date_str}"
        pub = _rfc2822(ub.created_at or datetime.now(timezone.utc))
        items_xml.append(
            f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <guid isPermaLink="false">briefing-{feed_token[:8]}-{date_str}</guid>
      <pubDate>{pub}</pubDate>
      <enclosure url="{escape(audio_url)}" type="{mime}" length="0" />
      <itunes:explicit>false</itunes:explicit>
    </item>"""
        )

    body = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Mein Saganta-Briefing</title>
    <link>{escape(base)}</link>
    <atom:link xmlns:atom="http://www.w3.org/2005/Atom" href="{escape(self_url)}" rel="self" type="application/rss+xml" />
    <description>Dein persönliches, tägliches Nachrichten-Briefing zum Anhören.</description>
    <language>de-de</language>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>Saganta</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="News" />
{body}
  </channel>
</rss>"""
