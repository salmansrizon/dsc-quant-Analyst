"""Multi-channel notifier fan-out (#78) — staging's engine + main's channels."""
import types


def _stub_common(monkeypatch, prefs):
    from backend import notifications_service as ns, notification_prefs_service as nps
    import backend.user_service as us
    monkeypatch.setattr(nps, "get_prefs", lambda uid: prefs)
    monkeypatch.setattr(us, "get_user_by_id",
                        lambda uid: types.SimpleNamespace(email="u@example.com"))
    monkeypatch.setattr(ns, "resolve", lambda *a, **k: None)


ALERT = {"id": "a1", "user_id": "u1", "symbol": "GP",
         "condition_json": '{"op":"above","value":250}', "current_price": 257.0}


def test_fans_out_to_each_enabled_channel(monkeypatch):
    from backend import alert_checker, notifications_service as ns, email_sender
    from backend.notifications import channels
    sent = []
    _stub_common(monkeypatch, {"channels_enabled": ["email", "telegram"],
                               "telegram_chat_id": "c1", "email": "u@example.com"})
    ids = iter(["n1", "n2"])
    monkeypatch.setattr(ns, "begin", lambda **k: next(ids))
    monkeypatch.setattr(email_sender, "send_email", lambda *a: sent.append("email") or True)
    monkeypatch.setattr(channels, "send_telegram", lambda cid, msg: sent.append(("tg", cid)) or True)

    assert alert_checker.build_notifier()(ALERT) is True
    assert "email" in sent and ("tg", "c1") in sent


def test_channel_with_no_config_does_not_deliver(monkeypatch):
    from backend import alert_checker, notifications_service as ns
    from backend.notifications import channels
    _stub_common(monkeypatch, {"channels_enabled": ["telegram"], "telegram_chat_id": None})
    monkeypatch.setattr(ns, "begin", lambda **k: "n1")
    monkeypatch.setattr(channels, "send_telegram", lambda cid, msg: True)
    # telegram enabled but no chat_id → _send returns False → not delivered → retries.
    assert alert_checker.build_notifier()(ALERT) is False


def test_a_channel_already_sent_counts_as_delivered(monkeypatch):
    from backend import alert_checker, notifications_service as ns
    _stub_common(monkeypatch, {"channels_enabled": ["email"], "email": "u@example.com"})
    monkeypatch.setattr(ns, "begin", lambda **k: None)  # lock: already sent this crossing
    assert alert_checker.build_notifier()(ALERT) is True


def test_default_channel_is_email_when_no_prefs(monkeypatch):
    from backend import alert_checker, notifications_service as ns, email_sender
    sent = []
    _stub_common(monkeypatch, None)  # no prefs row
    monkeypatch.setattr(ns, "begin", lambda **k: (sent.append(k["channel"]), "n1")[1])
    monkeypatch.setattr(email_sender, "send_email", lambda *a: True)
    assert alert_checker.build_notifier()(ALERT) is True
    assert sent == ["email"]
