"""Telegram notifications — trade, error, watchdog and feed events.

A thin wrapper over the Telegram Bot API. Notifications are best-effort: a
delivery failure is logged and swallowed, never propagated, so a flaky
network can never disrupt trading.
"""

import json
import logging
import urllib.request
from collections.abc import Callable

log = logging.getLogger("capital.notify.telegram")

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

#: A transport sends one message: `(url, json_payload) -> None`.
Transport = Callable[[str, dict[str, object]], None]


def _urllib_transport(url: str, payload: dict[str, object]) -> None:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(  # noqa: S310 — fixed https Telegram API URL
        url, data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(request, timeout=10).close()  # noqa: S310


class TelegramNotifier:
    """Sends messages to a Telegram chat. A no-op until configured."""

    def __init__(
        self,
        token: str = "",
        chat_id: str = "",
        *,
        transport: Transport = _urllib_transport,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: object) -> "TelegramNotifier":
        return cls(
            getattr(settings, "telegram_bot_token", ""),
            getattr(settings, "telegram_chat_id", ""),
        )

    @property
    def enabled(self) -> bool:
        """Whether both a bot token and a chat id are configured."""
        return bool(self._token and self._chat_id)

    def send(self, text: str) -> bool:
        """Send `text`; return whether it was delivered.

        Returns False (without raising) when disabled or on any delivery
        failure — a notification must never break the caller.
        """
        if not self.enabled:
            return False
        try:
            self._transport(
                _API_URL.format(token=self._token),
                {"chat_id": self._chat_id, "text": text},
            )
            return True
        except Exception:  # noqa: BLE001 — a notification failure is non-fatal
            log.warning("telegram notification failed", exc_info=True)
            return False
