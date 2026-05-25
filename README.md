# lob-client

Python client for subscribing to live LOB model signals. Self-contained:
only depends on `websockets`.

## Install

```bash
uv add https://github.com/TUNI-Financial-Computing/lob-client.git
# or
pip install git+https://github.com/TUNI-Financial-Computing/lob-client.git
```

## Usage

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
    model_id="my-model-v1",
) as sub:
    while True:
        event = sub.read()
        if isinstance(event, Signal):
            print(event.signal, event.confidence)
```

See [`docs/`](docs/) for the full documentation, or build it with
`mkdocs serve` from the `docs/` directory.
