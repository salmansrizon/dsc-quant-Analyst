"""Notification content templates (#98): one template family, three renderers."""
from backend.notifications import templates


def test_alert_email_headline_why_stats_and_cta(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    n = templates.AlertNotification(symbol="GP", ltp=312.4, target=300.0, direction="above")

    subject, html = templates.alert_email(n)

    assert subject == "GP price alert triggered"
    assert "GP crossed your above target" in html          # headline
    assert "312.40" in html and "300.00" in html            # supporting numbers, no data dump
    assert "https://portal.test/stock/GP" in html            # CTA back to the portal
    assert "Not financial advice" in html                    # #84 non-negotiable disclaimer


def test_alert_email_colors_the_current_price_by_which_side_of_target(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    above = templates.AlertNotification(symbol="GP", ltp=310.0, target=300.0, direction="above")
    below = templates.AlertNotification(symbol="GP", ltp=290.0, target=300.0, direction="below")

    _, html_above = templates.alert_email(above)
    _, html_below = templates.alert_email(below)

    assert "#10b981" in html_above   # 310 > 300 -> green
    assert "#ef4444" in html_below   # 290 < 300 -> red


def test_alert_text_is_terse_and_carries_the_portal_link(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    n = templates.AlertNotification(symbol="GP", ltp=312.4, target=300.0, direction="above")

    text = templates.alert_text(n)

    assert text.count("\n") == 2                             # 3 lines: headline, why, link
    assert text.endswith("https://portal.test/stock/GP")
    assert "GP crossed your above target" in text


def test_digest_email_summarizes_pnl_and_top_mover_only(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    n = templates.DigestNotification(
        portfolio_pnl=125.5,
        top_gainers=[{"Symbol": "RENATA", "ChangePct": 6.7}, {"Symbol": "ACI", "ChangePct": 4.2}],
        top_losers=[{"Symbol": "SQUARE", "ChangePct": -3.1}],
    )

    subject, html = templates.digest_email(n)

    assert subject == "Your daily market digest"
    assert "+125.50" in html
    assert "RENATA" in html and "+6.7%" in html
    assert "SQUARE" in html and "-3.1%" in html
    assert "ACI" not in html                                  # top mover only, not a data dump
    assert "https://portal.test" in html


def test_digest_email_handles_no_movers_gracefully(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    n = templates.DigestNotification(portfolio_pnl=-40.0)

    subject, html = templates.digest_email(n)

    assert subject == "Your daily market digest"
    assert "-40.00" in html


def test_digest_text_is_terse_top_mover_only(monkeypatch):
    monkeypatch.setattr(templates, "PORTAL_URL", "https://portal.test")
    n = templates.DigestNotification(
        portfolio_pnl=125.5,
        top_gainers=[{"Symbol": "RENATA", "ChangePct": 6.7}],
        top_losers=[{"Symbol": "SQUARE", "ChangePct": -3.1}],
    )

    text = templates.digest_text(n)

    assert "RENATA" in text and "SQUARE" in text
    assert text.endswith("https://portal.test")
