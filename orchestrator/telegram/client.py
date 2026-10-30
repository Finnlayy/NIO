"""Telegram-Client-Port und Implementierungen.

- TelegramPort: Protocol
- FakeTelegramClient: In-Memory, für Tests
- TelethonClient: Lazy Wrapper für das Telethon-Modul. Darf secrets in Logs
  oder Returns nicht leaken.
"""

from __future__ import annotations

import datetime
from collections.abc import Awaitable, Callable
from typing import Any, Literal, NoReturn, Protocol

from core.protocol import format_timestamp, utc_now_iso

from .config import TelegramConfig
from .models import LoginState, TgDialog, TgMessage, normalize_peer


class TelegramError(Exception):
    """Basis-Klasse für Telegram-Fehler."""


class TelegramFloodWait(TelegramError):
    def __init__(self, seconds: int):
        super().__init__(f"Warten wegen FloodWait erforderlich: {seconds} Sekunden")
        self.seconds = seconds


class TelegramNotAuthorized(TelegramError):
    pass


class TelegramUnavailable(TelegramError):
    """Telethon ist nicht installiert (Extra ``telegram``)."""


class TelegramPort(Protocol):
    async def status(self) -> LoginState: ...
    async def me(self) -> dict[str, Any] | None: ...
    async def dialogs(self) -> list[TgDialog]: ...
    async def messages_since(self, peer: int | str, min_id: int, limit: int = 200) -> list[TgMessage]: ...
    async def send(self, peer: int | str, text: str) -> TgMessage: ...
    def on_new_message(self, callback: Callable[[TgMessage], Awaitable[None]]) -> None: ...
    async def close(self) -> None: ...


class FakeTelegramClient:
    def __init__(self) -> None:
        self.state = LoginState.AUTHORIZED
        self.me_data: dict[str, Any] | None = {"id": 1, "name": "Fake", "username": "fake"}
        self.fake_dialogs: list[TgDialog] = []
        self.fake_messages: list[TgMessage] = []
        self.sent: list[tuple[int | str, str]] = []
        self.callbacks: list[Callable[[TgMessage], Awaitable[None]]] = []
        self.flood_wait_after: int | None = None
        self._send_count = 0

    async def status(self) -> LoginState:
        return self.state

    async def me(self) -> dict[str, Any] | None:
        return self.me_data

    async def dialogs(self) -> list[TgDialog]:
        return self.fake_dialogs

    async def messages_since(self, peer: int | str, min_id: int, limit: int = 200) -> list[TgMessage]:
        res = []
        for m in self.fake_messages:
            if m.peer == peer and m.msg_id > min_id:
                res.append(m)
        res.sort(key=lambda m: m.msg_id)
        return res[:limit]

    async def send(self, peer: int | str, text: str) -> TgMessage:
        if self.flood_wait_after is not None and self._send_count >= self.flood_wait_after:
            raise TelegramFloodWait(30)
        self._send_count += 1

        self.sent.append((peer, text))
        return TgMessage(
            peer=peer if isinstance(peer, int) else hash(peer),
            msg_id=1000 + len(self.sent),
            sender="Fake",
            text=text,
            ts=utc_now_iso(),
            outgoing=True,
            is_bot=False,
        )

    def on_new_message(self, callback: Callable[[TgMessage], Awaitable[None]]) -> None:
        self.callbacks.append(callback)

    async def push(self, msg: TgMessage) -> None:
        self.fake_messages.append(msg)
        for cb in self.callbacks:
            await cb(msg)

    async def close(self) -> None:
        self.state = LoginState.DISCONNECTED


# Rueckwaertskompatibler Alias; die Logik lebt in models.normalize_peer.
_normalize_peer = normalize_peer


def _import_telethon() -> Any:
    try:
        import telethon
    except ImportError:
        raise TelegramUnavailable("telethon fehlt: pip install 'neu[telegram]'") from None
    return telethon


class TelethonClient:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self._client: Any = None
        self._state = LoginState.UNCONFIGURED
        self._callbacks: list[Callable[[TgMessage], Awaitable[None]]] = []
        self._flood_wait_until: str | None = None

        if self.config.configured:
            self._state = LoginState.DISCONNECTED

    @property
    def flood_wait_until(self) -> str | None:
        return self._flood_wait_until

    def _ensure_dir(self) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.data_dir.chmod(0o700)

    def _flood(self, seconds: int) -> NoReturn:
        until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=seconds)
        self._flood_wait_until = format_timestamp(until)
        raise TelegramFloodWait(seconds)

    async def _init_client(self) -> None:
        if self._client is not None:
            return

        telethon = _import_telethon()
        self._ensure_dir()
        session_str = str(self.config.session_path)

        self._client = telethon.TelegramClient(
            session_str,
            self.config.api_id,
            self.config.api_hash,
        )

        await self._client.connect()

        if self.config.session_path.exists():
            self.config.session_path.chmod(0o600)

        is_auth = await self._client.is_user_authorized()
        if is_auth:
            self._state = LoginState.AUTHORIZED
        else:
            self._state = LoginState.DISCONNECTED

        @self._client.on(telethon.events.NewMessage)
        async def handler(event: Any) -> None:
            msg = await self._serialize_message(event.message)
            if msg:
                for cb in self._callbacks:
                    await cb(msg)

    async def status(self) -> LoginState:
        if not self.config.configured:
            return LoginState.UNCONFIGURED
        if self._client is None:
            await self._init_client()
        return self._state

    async def me(self) -> dict[str, Any] | None:
        if self._state != LoginState.AUTHORIZED:
            return None
        me_obj = await self._client.get_me()
        if not me_obj:
            return None
        return {"id": me_obj.id, "name": me_obj.first_name or "", "username": me_obj.username or ""}

    async def dialogs(self) -> list[TgDialog]:
        if self._state != LoginState.AUTHORIZED:
            raise TelegramNotAuthorized("Client ist nicht eingeloggt")

        res = []
        async for dialog in self._client.iter_dialogs():
            kind: Literal["user", "group", "channel"] = "user"
            if dialog.is_group:
                kind = "group"
            elif dialog.is_channel:
                kind = "channel"

            res.append(
                TgDialog(
                    id=dialog.id,
                    name=dialog.name or "",
                    kind=kind,
                    is_bot=bool(getattr(dialog.entity, "bot", False)),
                    unread=dialog.unread_count,
                )
            )
        return res

    async def _serialize_message(self, message: Any) -> TgMessage | None:
        from telethon.utils import get_peer_id

        if not message.text:
            return None

        peer = get_peer_id(message.peer_id)
        # Gleiches Format wie utc_now_iso: der Store vergleicht Zeitstempel als Strings.
        ts = format_timestamp(message.date)

        sender = ""
        sender_obj = message.sender
        if sender_obj:
            sender = getattr(sender_obj, "username", "") or getattr(sender_obj, "first_name", "") or str(message.sender_id)

        return TgMessage(
            peer=peer,
            msg_id=message.id,
            sender=sender,
            text=message.text,
            ts=ts,
            outgoing=bool(message.out),
            is_bot=bool(getattr(sender_obj, "bot", False)),
        )

    async def messages_since(self, peer: int | str, min_id: int, limit: int = 200) -> list[TgMessage]:
        if self._state != LoginState.AUTHORIZED:
            raise TelegramNotAuthorized("Client ist nicht eingeloggt")

        norm_peer = normalize_peer(peer)
        res = []

        telethon = _import_telethon()
        try:
            async for msg in self._client.iter_messages(norm_peer, min_id=min_id, limit=limit, reverse=True):
                smsg = await self._serialize_message(msg)
                if smsg:
                    res.append(smsg)
        except telethon.errors.FloodWaitError as e:
            self._flood(e.seconds)

        return res

    async def send(self, peer: int | str, text: str) -> TgMessage:
        if self._state != LoginState.AUTHORIZED:
            raise TelegramNotAuthorized("Client ist nicht eingeloggt")

        norm_peer = normalize_peer(peer)

        telethon = _import_telethon()
        try:
            sent_msg = await self._client.send_message(norm_peer, text)
            smsg = await self._serialize_message(sent_msg)
            if not smsg:
                from telethon.utils import get_peer_id

                smsg = TgMessage(
                    peer=get_peer_id(sent_msg.peer_id),
                    msg_id=sent_msg.id,
                    sender="Me",
                    text=text,
                    ts=utc_now_iso(),
                    outgoing=True,
                    is_bot=False,
                )
            return smsg
        except telethon.errors.FloodWaitError as e:
            self._flood(e.seconds)

    def on_new_message(self, callback: Callable[[TgMessage], Awaitable[None]]) -> None:
        self._callbacks.append(callback)

    async def close(self) -> None:
        if self._client:
            await self._client.disconnect()
        self._state = LoginState.DISCONNECTED

    async def send_code(self, phone: str) -> None:
        if not self.config.configured:
            raise ValueError("Telegram nicht konfiguriert")
        await self._init_client()

        telethon = _import_telethon()
        try:
            self._phone = phone
            res = await self._client.send_code_request(phone)
            self._phone_code_hash = res.phone_code_hash
            self._state = LoginState.CODE_SENT
        except telethon.errors.PhoneNumberInvalidError:
            raise ValueError("Telefonnummer ungültig.") from None
        except telethon.errors.FloodWaitError as e:
            self._flood(e.seconds)

    async def sign_in_code(self, code: str) -> None:
        if self._state != LoginState.CODE_SENT:
            raise ValueError("Falscher Zustand: Code noch nicht gesendet")

        telethon = _import_telethon()
        try:
            await self._client.sign_in(phone=self._phone, code=code, phone_code_hash=self._phone_code_hash)
            self._state = LoginState.AUTHORIZED
        except telethon.errors.PhoneCodeInvalidError:
            raise ValueError("Code falsch") from None
        except telethon.errors.PhoneCodeExpiredError:
            self._state = LoginState.DISCONNECTED
            raise ValueError("Code abgelaufen") from None
        except telethon.errors.SessionPasswordNeededError:
            self._state = LoginState.NEEDS_PASSWORD

    async def sign_in_password(self, password: str) -> None:
        if self._state != LoginState.NEEDS_PASSWORD:
            raise ValueError("Falscher Zustand: Passwort nicht erforderlich")

        telethon = _import_telethon()
        try:
            await self._client.sign_in(password=password)
            self._state = LoginState.AUTHORIZED
        except telethon.errors.PasswordHashInvalidError:
            raise ValueError("2FA-Passwort falsch.") from None
        except telethon.errors.FloodWaitError as e:
            self._flood(e.seconds)

    async def logout(self) -> None:
        if self._client:
            await self._client.log_out()
        self._state = LoginState.DISCONNECTED
