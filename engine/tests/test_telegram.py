"""Tests for the Telegram notifier."""

from notify.telegram import TelegramNotifier


def test_disabled_notifier_sends_nothing() -> None:
    notifier = TelegramNotifier()  # no token / chat id
    assert notifier.enabled is False
    assert notifier.send("hello") is False


def test_enabled_notifier_calls_the_transport() -> None:
    sent: list[tuple[str, dict[str, object]]] = []
    notifier = TelegramNotifier(
        "bot-token", "chat-99", transport=lambda url, payload: sent.append((url, payload))
    )
    assert notifier.enabled is True
    assert notifier.send("a trade happened") is True
    assert len(sent) == 1
    url, payload = sent[0]
    assert "bot-token" in url
    assert payload["chat_id"] == "chat-99"
    assert payload["text"] == "a trade happened"


def test_transport_failure_is_swallowed() -> None:
    def boom(_url: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("network down")

    notifier = TelegramNotifier("t", "c", transport=boom)
    assert notifier.send("hi") is False  # logged, not raised


def test_from_settings() -> None:
    class _S:
        telegram_bot_token = "token"
        telegram_chat_id = "chat"

    assert TelegramNotifier.from_settings(_S()).enabled is True
