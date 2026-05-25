# Label specs

A **label spec** describes the prediction task a model is trained for:
how the future price is summarised, over what horizon, with what
threshold, and so on. The server uses the spec's `task_id` to route
your signal subscription to the right model output.

All spec types live in `lob_client.specs` and are re-exported from the
top-level `lob_client` package.

## Building a spec

Pick the spec that matches the model you want to subscribe to and
construct it from the building blocks ([`IndexSpec`][lob_client.IndexSpec],
[`ThresholdSpec`][lob_client.ThresholdSpec], plus a handful of enums).

```python
from lob_client import (
    IndexSpec,
    MidpriceMoveThreeClassSpec,
    ReferenceMode,
    SmoothMethod,
    ThresholdSpec,
)

label_spec = MidpriceMoveThreeClassSpec(
    horizon=IndexSpec.events(100),
    delay=IndexSpec.events(0),
    reference_mode=ReferenceMode.ANCHOR,
    threshold=ThresholdSpec.absolute_ticks(2.0),
    smoothing=SmoothMethod.LAST,
)
```

Then hand the spec to [`Client.subscribe_signals`][lob_client.Client.subscribe_signals]:

```python
with client.subscribe_signals(
    symbol="ETH/USD",
    label_spec=label_spec,
    model_id="mbo-model:latest",
) as sub:
    ...
```

## Available specs

| Spec                                                                 | Classes | Notes                                                       |
| -------------------------------------------------------------------- | ------- | ----------------------------------------------------------- |
| [`MidpriceMoveThreeClassSpec`][lob_client.MidpriceMoveThreeClassSpec] | 3       | Mid-price move up / flat / down over a horizon.              |
| [`MidpriceTwoClassSpec`][lob_client.MidpriceTwoClassSpec]             | 2       | Mid-price above / below threshold at delay.                  |
| [`SpreadCrossTwoClassSpec`][lob_client.SpreadCrossTwoClassSpec]       | 2       | First spread-cross direction (currently `FIRST_MOVE` only).  |
| [`SpreadCrossThreeClassSpec`][lob_client.SpreadCrossThreeClassSpec]   | 3       | Spread-cross with up / flat / down outcomes.                 |

## Building blocks

### Index spec

[`IndexSpec`][lob_client.IndexSpec] picks an index space and a value.
Use the helpers:

```python
IndexSpec.events(100)        # 100 events
IndexSpec.nanoseconds(5_000) # 5 microseconds
```

### Threshold spec

[`ThresholdSpec`][lob_client.ThresholdSpec] describes the move size.
Three constructors cover the common cases:

```python
ThresholdSpec.absolute_ticks(2.0)   # 2 ticks
ThresholdSpec.absolute_price(0.05)  # 5 cents
ThresholdSpec.relative(0.001)       # 10 bps
```

### Enums

* [`IndexSpace`][lob_client.IndexSpace] — `EVENT` or `TIME`.
* [`ReferenceMode`][lob_client.ReferenceMode] — `ANCHOR` or `BEFORE_WINDOW_START`.
* [`ThresholdMode`][lob_client.ThresholdMode] — `ABSOLUTE` or `RELATIVE`.
* [`ThresholdSpace`][lob_client.ThresholdSpace] — `PRICE` or `TICK`.
* [`SmoothMethod`][lob_client.SmoothMethod] — `LAST`, `MEAN`, `EXTREMUM`, `FIRST_MOVE`.
* [`CrossSelection`][lob_client.CrossSelection] — `FIRST_MOVE`, `LAST_MOVE`, `EXTREMUM`.

## Serialisation

Every spec implements `to_dict()` and `from_dict()` so you can round-trip
through JSON or YAML, plus `task_id()` which returns the deterministic
string the server uses for routing:

```python
label_spec.task_id()
# 'mp3_he100_de0_ref-a_thr-a2.0t_sm-l'
```
