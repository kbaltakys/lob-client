from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StreamEvent:
    type: str
    lob_client_recv_timestamp_ns: int

    def __post_init__(self):
        if not isinstance(self.lob_client_recv_timestamp_ns, int):
            raise ValueError("lob_client_recv_timestamp_ns must be an integer")
        if self.lob_client_recv_timestamp_ns < 0:
            raise ValueError("lob_client_recv_timestamp_ns must be non-negative")


@dataclass
class AuthenticationAck(StreamEvent):
    client_id: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> AuthenticationAck:
        return AuthenticationAck(
            type=d["type"],
            client_id=d["client_id"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
        )


@dataclass
class SignalSubscribed(StreamEvent):
    symbol: str
    signal_subscription_id: int
    task_id: str
    model_id: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> SignalSubscribed:
        return SignalSubscribed(
            type=d["type"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
            symbol=d["symbol"],
            signal_subscription_id=d["signal_subscription_id"],
            task_id=d["task_id"],
            model_id=d.get("model_id"),
        )


@dataclass
class Signal(StreamEvent):
    signal_subscription_id: int
    symbol: str
    task_id: str
    model_id: str
    signal: int
    confidence: float
    signal_valid_from_ns: int
    signal_valid_to_ns: int
    exchange_timestamp_ns: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Signal:
        return Signal(
            type=d["type"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
            signal_subscription_id=d["signal_subscription_id"],
            symbol=d["symbol"],
            task_id=d["task_id"],
            model_id=d["model_id"],
            signal=d["signal"],
            confidence=d["confidence"],
            signal_valid_from_ns=d["signal_valid_from_ns"],
            signal_valid_to_ns=d["signal_valid_to_ns"],
            exchange_timestamp_ns=d["exchange_timestamp_ns"],
        )


@dataclass
class SignalWarning(StreamEvent):
    signal_subscription_id: int
    symbol: str
    message: str
    dropped: int

    @staticmethod
    def from_dict(d: dict[str, Any]) -> SignalWarning:
        return SignalWarning(
            type=d["type"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
            signal_subscription_id=d["signal_subscription_id"],
            symbol=d["symbol"],
            message=d["message"],
            dropped=d["dropped"],
        )


@dataclass
class StreamError(StreamEvent):
    symbol: str | None
    stream_id: int | None
    upstream_topic_instance_id: int | None
    message: str
    recoverable: bool = True

    @staticmethod
    def from_dict(d: dict[str, Any]) -> StreamError:
        return StreamError(
            type=d["type"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
            symbol=d.get("symbol"),
            stream_id=d.get("stream_id"),
            upstream_topic_instance_id=d.get("upstream_topic_instance_id"),
            message=d.get("message", "stream failed"),
            recoverable=d.get("recoverable", True),
        )


@dataclass
class ControlEvent(StreamEvent):
    payload: dict[str, Any]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ControlEvent:
        return ControlEvent(
            type=d["type"],
            lob_client_recv_timestamp_ns=d["lob_client_recv_timestamp_ns"],
            payload=d,
        )


def parse_stream_event(payload: dict[str, Any]) -> StreamEvent:
    event_type = payload.get("type")

    if event_type == "authenticated":
        return AuthenticationAck.from_dict(payload)
    if event_type == "signal_subscribed":
        return SignalSubscribed.from_dict(payload)
    if event_type == "signal":
        return Signal.from_dict(payload)
    if event_type == "signal_warning":
        return SignalWarning.from_dict(payload)
    if event_type == "stream_error":
        return StreamError.from_dict(payload)

    if isinstance(event_type, str):
        return ControlEvent.from_dict(payload)
    raise ValueError(f"Unknown event type: {event_type} in message {payload}")
