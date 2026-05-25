class LobClientError(RuntimeError):
    pass


class LobStreamError(LobClientError):
    pass


class LobTimeoutError(LobStreamError, TimeoutError):
    pass


class ConnectionClosed(LobStreamError):
    pass


class StreamFailed(LobStreamError):
    pass


class StreamIdleTimeout(LobStreamError):
    pass
