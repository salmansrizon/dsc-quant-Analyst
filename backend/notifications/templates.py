"""Notification content templates (#98): one template family — a shared,
provider-agnostic content shape per notification type — three renderers (HTML
email, Telegram text, WhatsApp text share one plain-text renderer, since
neither channel has parse_mode/markdown wired up in #94's senders yet).
Feeds the sends #94 proved. Replaces the old messages.py.

Design decisions, following #87's branding into a non-app-chrome context:
- **Email** renders on a plain white shell using the app's LIGHT-theme accent
  hex values (src/index.css), not the app's own dark default — email clients'
  dark-mode support is inconsistent across Gmail/Outlook/Apple Mail, so a
  branded light shell is the one that reliably reads correctly everywhere.
  Structure per the ticket: headline, one-line "why", 1-2 supporting numbers,
  one CTA button back to the portal. No data dump.
- **Telegram/WhatsApp** render the same content as terse plain text ending in
  a link back to the portal — summary-only, matching the ticket's "not
  bored or bombarded" anti-goal. The digest trims to just the #1 gainer/#1
  loser (the old messages.build_digest_message showed top 5 of each, which
  is closer to a data dump than a summary).
"""
import os
from dataclasses import dataclass, field

PORTAL_URL = os.environ.get("PORTAL_URL", "https://dsc-quant.example").rstrip("/")

# Light-theme brand hex values (src/index.css :root, the light palette) — the
# one hardcoded copy of these an email template needs, since email clients
# don't reliably resolve CSS custom properties.
_BLUE = "#2563eb"
_GREEN = "#10b981"
_RED = "#ef4444"
_TEXT = "#1a1a1a"
_MUTED = "#666666"
_BORDER = "#e5e7eb"


def _signed_color(value: float) -> str:
    return _GREEN if value >= 0 else _RED


def _email_shell(headline: str, why: str, stats: list[tuple[str, str, str | None]],
                 cta_label: str, cta_url: str) -> str:
    """The one HTML shell every email notification renders through — brand
    mark, headline, one-line why, a small stats row, one CTA button, and the
    not-advice footer. `stats` is (label, value, color) triples; color None
    uses the default text color."""
    stat_cells = "".join(
        f'<td style="padding:0 20px 0 0;"><div style="font-size:12px;color:{_MUTED};">{label}</div>'
        f'<div style="font-size:18px;font-weight:600;color:{color or _TEXT};">{value}</div></td>'
        for label, value, color in stats
    )
    return f"""
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
  <div style="font-size:12px;font-weight:700;letter-spacing:0.05em;color:{_BLUE};text-transform:uppercase;">DSC Quant Analyst</div>
  <h1 style="font-size:20px;font-weight:700;color:{_TEXT};margin:12px 0 4px;">{headline}</h1>
  <p style="font-size:14px;color:{_MUTED};margin:0 0 20px;">{why}</p>
  <table style="margin-bottom:24px;" cellpadding="0" cellspacing="0"><tr>{stat_cells}</tr></table>
  <a href="{cta_url}" style="display:inline-block;background:{_BLUE};color:#ffffff;font-weight:600;font-size:14px;text-decoration:none;padding:10px 20px;border-radius:8px;">{cta_label} &rarr;</a>
  <p style="font-size:11px;color:{_MUTED};margin-top:28px;border-top:1px solid {_BORDER};padding-top:12px;">
    Not financial advice — informational alerts only.
  </p>
</div>
""".strip()


@dataclass
class AlertNotification:
    symbol: str
    ltp: float
    target: float
    direction: str  # 'above' | 'below'


def _alert_headline(n: AlertNotification) -> str:
    return f"{n.symbol} crossed your {n.direction} target"


def _alert_why(n: AlertNotification) -> str:
    arrow = "↑" if n.direction == "above" else "↓"
    return f"{arrow} Now {n.ltp:.2f}, {n.direction} your target of {n.target:.2f}."


def _alert_url(n: AlertNotification) -> str:
    return f"{PORTAL_URL}/stock/{n.symbol}"


def alert_email(n: AlertNotification) -> tuple[str, str]:
    """(subject, html)."""
    subject = f"{n.symbol} price alert triggered"
    html = _email_shell(
        headline=_alert_headline(n), why=_alert_why(n),
        stats=[("Current", f"{n.ltp:.2f}", _signed_color(n.ltp - n.target)),
               ("Target", f"{n.target:.2f}", None)],
        cta_label="View on the portal", cta_url=_alert_url(n),
    )
    return subject, html


def alert_text(n: AlertNotification) -> str:
    return f"🔔 {_alert_headline(n)}\n{_alert_why(n)}\n{_alert_url(n)}"


@dataclass
class DigestNotification:
    portfolio_pnl: float
    top_gainers: list[dict] = field(default_factory=list)
    top_losers: list[dict] = field(default_factory=list)


def _digest_why(n: DigestNotification) -> str:
    sign = "+" if n.portfolio_pnl >= 0 else ""
    return f"Your portfolio moved {sign}{n.portfolio_pnl:.2f} today."


def digest_email(n: DigestNotification) -> tuple[str, str]:
    stats: list[tuple[str, str, str | None]] = [
        ("Portfolio P&L", f"{n.portfolio_pnl:+.2f}", _signed_color(n.portfolio_pnl)),
    ]
    if n.top_gainers:
        g = n.top_gainers[0]
        stats.append((f"Top gainer: {g['Symbol']}", f"+{g['ChangePct']:.1f}%", _GREEN))
    if n.top_losers:
        l = n.top_losers[0]
        stats.append((f"Top loser: {l['Symbol']}", f"{l['ChangePct']:.1f}%", _RED))
    html = _email_shell(
        headline="Your daily market digest", why=_digest_why(n),
        stats=stats, cta_label="Open the portal", cta_url=PORTAL_URL,
    )
    return "Your daily market digest", html


def digest_text(n: DigestNotification) -> str:
    lines = [f"📊 Daily digest — {_digest_why(n)}"]
    if n.top_gainers:
        g = n.top_gainers[0]
        lines.append(f"Top gainer: {g['Symbol']} +{g['ChangePct']:.1f}%")
    if n.top_losers:
        l = n.top_losers[0]
        lines.append(f"Top loser: {l['Symbol']} {l['ChangePct']:.1f}%")
    lines.append(PORTAL_URL)
    return "\n".join(lines)
