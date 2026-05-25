from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional

from websockets.sync.client import connect as ws_connect

from .specs import LabelSpec
from .errors import (
    ConnectionClosed,
    LobStreamError,
    LobTimeoutError,
    StreamIdleTimeout,
)
from .types import (
    SignalSubscribed,
    StreamEvent,
    parse_stream_event,
)


def _label_spec_to_dict(label_spec: LabelSpec | None) -> dict[str, Any] | None:
    if label_spec is None:
        return None
    if isinstance(label_spec, Mapping):
        return dict(label_spec)

    to_dict = getattr(label_spec, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if not isinstance(payload, dict):
            raise TypeError("label_spec.to_dict() must return a dict")
        return payload

    raise TypeError("label_spec must be a dict or an object with to_dict()")


def _current_timestamp_ns() -> int:
    return time.time_ns()


@dataclass(frozen=True)
class Client:
    """Entry point for connecting to the signal service.

    Use :meth:`subscribe_signals` to open a signal subscription.
    """

    token: str
    url_local: str = field(default="ws://127.0.0.1:443")
    url_remote: str = field(default="ws://api.tradingepoch.com:4443")
    local: bool = field(default=False)

    def subscribe_signals(
        self,
        symbol: str,
        label_spec: LabelSpec,
        model_id: str | None = None,
        *,
        recv_timeout: Optional[float] = None,
    ) -> SignalSubscription:
        """Open a connection, authenticate, and subscribe to model signals.

        Returns a started :class:`SignalSubscription`. Call ``.read()`` on the
        returned object to receive :class:`Signal` events.
        """
        url = self.url_local if self.local else self.url_remote
        sub = SignalSubscription(
            url=url,
            token=self.token,
            symbol=symbol,
            label_spec=label_spec,
            model_id=model_id,
            recv_timeout=recv_timeout,
        )
        sub._start()
        sub.subscribe_signals(
            symbol=symbol,
            label_spec=label_spec,
            model_id=model_id,
            wait=True,
        )
        return sub


class SignalSubscription:
    """A live websocket subscription to model signals for a single symbol.

    Typically constructed via :meth:`Client.subscribe_signals`. Supports use
    as a context manager: it will close the underlying websocket on exit.
    """

    def __init__(
        self,
        url: str,
        token: str,
        symbol: str,
        label_spec: Optional[LabelSpec] = None,
        model_id: str | None = None,
        *,
        recv_timeout: Optional[float] = None,
    ) -> None:
        assert isinstance(symbol, str), "symbol must be a string"
        self._url = url
        self._token = token
        self._symbol = symbol
        self._label_spec = label_spec
        self._model_id = model_id

        self._q: queue.Queue[object] = queue.Queue(maxsize=10_000)
        self._stop = threading.Event()
        self._thread_main: Optional[threading.Thread] = None
        self._ws = None  # type: ignore[assignment]
        self._send_lock = threading.Lock()

        self._authenticated = False
        self._recv_timeout = recv_timeout

    def __enter__(self) -> SignalSubscription:
        try:
            self._start()
            if self._label_spec is not None:
                self.subscribe_signals(
                    symbol=self._symbol,
                    label_spec=self._label_spec,
                    model_id=self._model_id,
                    wait=True,
                )
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def keywords(self) -> dict[str, Any]:
        return {"symbol": self._symbol, "model_id": self._model_id}

    def _start(self) -> None:
        if self._thread_main is not None:
            return

        t = threading.Thread(
            target=self._run, name=f"lob-client:{self.keywords}", daemon=True
        )
        self._thread_main = t
        t.start()

        auth = self._wait_for_types({"authenticated", "error"}, timeout=5.0)
        if auth.type == "error":
            raise LobStreamError("authentication failed")
        self._authenticated = True

    def _wait_for_types(self, accepted: set[str], timeout: float) -> StreamEvent:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LobTimeoutError(f"timeout waiting for events of type {accepted}")

            try:
                event = self.read(timeout=remaining)
            except LobTimeoutError as e:
                accepted_str = ", ".join(accepted)
                raise LobTimeoutError(
                    f"timeout waiting for events of type {accepted_str}"
                ) from e

            if event.type in accepted:
                return event
            if event.type == "error":
                return event

    def _send_json(self, payload: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None:
            raise ConnectionClosed("subscription is not connected")
        with self._send_lock:
            ws.send(json.dumps(payload))

    def _run(self) -> None:
        failed = False
        try:
            with ws_connect(
                self._url,
                open_timeout=10,
                ping_timeout=10,
                close_timeout=1,
            ) as ws:
                self._ws = ws
                self._send_json({"type": "authenticate", "token": self._token})

                while not self._stop.is_set():
                    try:
                        msg = ws.recv(timeout=self._recv_timeout)
                    except TimeoutError as e:
                        raise StreamIdleTimeout(
                            "no messages received within idle timeout"
                        ) from e
                    self._enqueue_parsed(msg)

        except Exception as e:
            failed = True
            self._enqueue(e)

        finally:
            self._ws = None
            if not failed:
                self._enqueue(
                    ConnectionClosed(f"subscription closed: {self.keywords}")
                )

    def _enqueue_parsed(self, msg: Any) -> None:
        if isinstance(msg, str) and msg.startswith("{"):
            try:
                payload = json.loads(msg)
                if isinstance(payload, dict):
                    payload["lob_client_recv_timestamp_ns"] = _current_timestamp_ns()
                    event = parse_stream_event(payload)
                    self._enqueue(event)
            except Exception as e:
                self._enqueue(e)
        else:
            self._enqueue(ValueError(f"unexpected message format: {msg}"))

    def _force_enqueue(self, item: object) -> None:
        if self._q.full():
            _ = self._q.get_nowait()
        self._q.put_nowait(item)

    def _enqueue(self, item: object) -> None:
        while not self._stop.is_set():
            try:
                self._q.put(item, timeout=0.1)
                return
            except queue.Full:
                try:
                    _ = self._q.get_nowait()
                except queue.Empty:
                    pass

    def read(self, timeout: Optional[float] = None) -> StreamEvent:
        """Block until the next event is available, then return it.

        Raises :class:`LobTimeoutError` if ``timeout`` elapses with no event.
        Raises :class:`ConnectionClosed` when the underlying socket has closed.
        """
        try:
            item = self._q.get(timeout=timeout)
        except queue.Empty as e:
            raise LobTimeoutError("read() timed out") from e

        if isinstance(item, LobStreamError):
            raise item

        if isinstance(item, Exception):
            if isinstance(item, ConnectionClosed):
                raise item
            raise LobStreamError(str(item)) from item
        if isinstance(item, StreamEvent):
            return item
        raise LobStreamError(f"unexpected message type: {type(item)} - {item}")

    def close(self) -> None:
        """Stop the background reader and close the websocket.

        Safe to call more than once. Called automatically when the
        subscription is used as a context manager.
        """
        self._stop.set()
        self._force_enqueue(ConnectionClosed(f"subscription closed: {self.keywords}"))
        ws = self._ws
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass

        t = self._thread_main
        if t is not None and t.is_alive():
            t.join(timeout=2.0)

    def subscribe_signals(
        self,
        *,
        symbol: str,
        label_spec: LabelSpec,
        model_id: str | None = None,
        wait: bool = True,
        timeout: float = 5.0,
    ) -> StreamEvent | None:
        """Send a ``signal_subscribe`` request after authentication.

        If ``wait=True`` (default), block until the server acknowledges with a
        :class:`SignalSubscribed` event and return it.
        """
        if self._thread_main is None:
            self._start()
        if not self._authenticated:
            raise LobStreamError("not authenticated")

        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be a non-empty string")

        label_spec_payload = _label_spec_to_dict(label_spec)
        if label_spec_payload is None:
            raise ValueError("label_spec is required for signal subscriptions")

        payload = {
            "type": "signal_subscribe",
            "symbol": symbol,
            "label_spec": label_spec_payload,
            "model_id": model_id,
        }

        self._send_json(payload)

        if not wait:
            return None

        event = self._wait_for_types({"signal_subscribed", "error"}, timeout=timeout)
        if event.type == "error":
            message = getattr(event, "payload", {}).get("message", "signal subscribe failed")
            raise LobStreamError(message)

        return event

    def unsubscribe_signals(
        self,
        signal_subscription_id: int,
        *,
        wait: bool = False,
        timeout: float = 5.0,
    ) -> StreamEvent | None:
        """Cancel a signal subscription by id."""
        if not isinstance(signal_subscription_id, int):
            raise ValueError("signal_subscription_id must be an integer")
        if signal_subscription_id < 0:
            raise ValueError("signal_subscription_id must be non-negative")

        self._send_json(
            {
                "type": "signal_unsubscribe",
                "signal_subscription_id": signal_subscription_id,
            }
        )

        if not wait:
            return None

        event = self._wait_for_types({"signal_unsubscribed", "error"}, timeout=timeout)
        if event.type == "error":
            message = getattr(event, "payload", {}).get(
                "message", "signal unsubscribe failed"
            )
            raise LobStreamError(message)

        return event
