"""Cancellation shared between a workbench run and its model connection."""

import socket
import threading


class Cancellation:
    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks = set()

    def is_set(self):
        return self._event.is_set()

    def cancel(self):
        with self._lock:
            self._event.set()
            callbacks = tuple(self._callbacks)
        for callback in callbacks:
            callback()

    def register_response(self, response):
        def interrupt():
            # shutdown wakes a concurrent iter_lines read before close tries to
            # acquire the buffered reader's lock. The generator owns close().
            try:
                response.raw._fp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
            except (AttributeError, OSError, ValueError):
                pass
        with self._lock:
            self._callbacks.add(interrupt)
            cancelled = self._event.is_set()
        if cancelled:
            interrupt()
        return interrupt

    def register_socket(self, sock):
        def interrupt():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, ValueError):
                pass
        with self._lock:
            self._callbacks.add(interrupt)
            cancelled = self._event.is_set()
        if cancelled:
            interrupt()
        return interrupt

    def unregister(self, callback):
        with self._lock:
            self._callbacks.discard(callback)


def cancellable_session(token):
    """Capture connected sockets, including while awaiting response headers."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.connection import HTTPConnection, HTTPSConnection
    from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

    callbacks = []
    class HTTP(HTTPConnection):
        def connect(self):
            super().connect()
            callbacks.append(token.register_socket(self.sock))
    class HTTPS(HTTPSConnection):
        def connect(self):
            super().connect()
            callbacks.append(token.register_socket(self.sock))
    class HTTPPool(HTTPConnectionPool):
        ConnectionCls = HTTP
    class HTTPSPool(HTTPSConnectionPool):
        ConnectionCls = HTTPS
    class Adapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            super().init_poolmanager(*args, **kwargs)
            self.poolmanager.pool_classes_by_scheme = {"http": HTTPPool, "https": HTTPSPool}
        def close(self):
            for callback in callbacks:
                token.unregister(callback)
            callbacks.clear()
            super().close()
    session = requests.Session()
    session.mount("http://", Adapter())
    session.mount("https://", Adapter())
    return session
