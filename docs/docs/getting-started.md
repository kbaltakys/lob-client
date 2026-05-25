# Getting started

## Installation

```bash
# with uv
uv add https://github.com/kbaltakys/lob-client

# with pip
pip install git+https://github.com/kbaltakys/lob-client
```

`lob-client` only depends on
[`websockets`](https://websockets.readthedocs.io/) at runtime. Label
specs (used to describe the model task) are bundled directly in
`lob_client.specs` — see [Label specs](label-specs.md).

## Authentication

The `Client` is constructed with an API token. By default it connects
to the public DeltaBerry endpoint:

```python
from lob_client import Client

client = Client(token="<your-token>")
```

## Next steps

Head over to [Subscribing to signals](signals.md) for a walkthrough of
how to start a subscription and consume signal events.
