# Subscribing to signals

A **signal** is a model's prediction for a given symbol and task,
delivered live over a websocket. Each signal carries the discrete
prediction, a confidence value, and a validity window in nanoseconds.

This page describes the full lifecycle: open a connection, subscribe,
read signals, and shut down cleanly.

## The high-level flow

```python
from lob_client import (
    Client,
    IndexSpec,
    MidpriceMoveThreeClassSpec,
    ReferenceMode,
    Signal,
    SmoothMethod,
    ThresholdSpec,
)

client = Client(token="letmein")

label_spec = MidpriceMoveThreeClassSpec(
    horizon=IndexSpec.events(100),
    delay=IndexSpec.events(0),
    reference_mode=ReferenceMode.ANCHOR,
    threshold=ThresholdSpec.absolute_ticks(2.0),
    smoothing=SmoothMethod.LAST,
)

with client.subscribe_signals(
    symbol="ETH/USD",
    label_spec=label_spec,
    model_id="mbo-model:latest",
) as sub:
    while True:
        event = sub.read()
        if isinstance(event, Signal):
            print(
                event.symbol,
                event.signal,
                event.confidence,
                event.signal_valid_from_ns,
                event.signal_valid_to_ns,
            )
```

[`Client.subscribe_signals`][lob_client.Client.subscribe_signals] does
three things for you:

1. Opens the websocket connection.
2. Sends `authenticate` and waits for the server's `authenticated` ack.
3. Sends `signal_subscribe` and waits for a `signal_subscribed` ack.

It then returns a started [`SignalSubscription`][lob_client.SignalSubscription]
you can read from.

## Reading events

[`SignalSubscription.read`][lob_client.SignalSubscription.read] blocks
until the next event arrives. You can pass `timeout=` to limit how long
it waits:

```python
from lob_client import LobTimeoutError

try:
    event = sub.read(timeout=1.0)
except LobTimeoutError:
    print("no signal in the last second")
```

### Event types you may receive

| Type                | Description                                           |
| ------------------- | ----------------------------------------------------- |
| `Signal`            | A model prediction for one packet.                    |
| `SignalSubscribed`  | Ack that the subscription is live (handled for you).  |
| `SignalWarning`     | Server-side warning, e.g. dropped signals.            |
| `StreamError`       | Server-side stream error.                             |
| `ControlEvent`      | Any other control message from the server.           |

Filter on type with `isinstance`:

```python
from lob_client import Signal, SignalWarning

while True:
    event = sub.read()
    if isinstance(event, Signal):
        handle_signal(event)
    elif isinstance(event, SignalWarning):
        log.warning("server dropped %d signals: %s", event.dropped, event.message)
```

## Lifecycle

### Context manager (recommended)

Using `with` makes sure the background thread and websocket are torn
down whether your loop exits normally or by exception:

```python
with client.subscribe_signals(...) as sub:
    ...
```

### Manual lifecycle

If you cannot use a context manager, you must call
[`close()`][lob_client.SignalSubscription.close] yourself:

```python
sub = client.subscribe_signals(...)
try:
    while True:
        event = sub.read()
        ...
finally:
    sub.close()
```

### Unsubscribing without closing

If you want to keep the connection open but drop the subscription, use
the `signal_subscription_id` from the `SignalSubscribed` ack:

```python
sub.unsubscribe_signals(signal_subscription_id, wait=True)
```

!!! note
    `Client.subscribe_signals` doesn't return the ack directly — if you
    need the id, call the lower-level
    [`SignalSubscription.subscribe_signals`][lob_client.SignalSubscription.subscribe_signals]
    yourself and read the return value.

## Errors

All errors raised by `lob-client` inherit from
[`LobClientError`][lob_client.LobClientError]. The ones you are most
likely to handle:

* [`LobTimeoutError`][lob_client.LobTimeoutError] — `read()` exceeded
  its timeout.
* [`ConnectionClosed`][lob_client.ConnectionClosed] — the websocket
  closed. The subscription is no longer usable.
* [`LobStreamError`][lob_client.LobStreamError] — server reported an
  error (e.g. authentication failure, invalid subscription).
* [`StreamIdleTimeout`][lob_client.StreamIdleTimeout] — set a
  `recv_timeout` on the subscription and no message arrived in time.

## Advanced: idle timeout

Pass `recv_timeout=` to detect a silent server. The background thread
raises [`StreamIdleTimeout`][lob_client.StreamIdleTimeout] (visible to
your next `read()` call) if no message arrives within that window:

```python
sub = client.subscribe_signals(
    symbol="ETH/USD",
    label_spec=label_spec,
    recv_timeout=30.0,  # seconds
)
```
