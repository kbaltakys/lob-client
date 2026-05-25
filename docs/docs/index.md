# lob-client

`lob-client` is a thin Python client for connecting to the LOB signal
service. It lets you authenticate, subscribe to a model's live signals
for a given symbol, and consume signal events from a background
websocket connection. `lob-client` is intentionally minimal
and focused on **signal consumption**.

## Quick example

```python
from lob_client import (
    Client,
    IndexSpec,
    MidpriceMoveThreeClassSpec,
    ReferenceMode,
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
        print(event)
```

## Where to next

* [Getting started](getting-started.md) — install and authenticate.
* [Subscribing to signals](signals.md) — full walkthrough of the
  signal subscription lifecycle.
* [Label specs](label-specs.md) — how to describe the prediction task
  you want signals for.
* [API reference](api.md) — auto-generated reference for the public
  classes and functions.
