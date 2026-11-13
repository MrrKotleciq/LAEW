# TCP frame reader
## Receiving a measurement frame
A TCP connection transports a byte stream, so one receive call is not a complete application-message boundary. The frame reader accumulates bytes until the required frame length has arrived. A shorter nonempty result is retained, rather than discarded as a corrupt frame. When recv returns an empty byte string, the peer has closed the connection. The application must distinguish this from a socket timeout; a timeout alone is not evidence of an orderly close.
## Sending and timeouts
Use sendall when the complete byte buffer must be submitted; send may report only a partial transfer. A configured socket timeout bounds blocking operations, but does not add message framing. The engineering adapter records how many bytes were assembled before abandoning a frame, so a later diagnostic can distinguish an incomplete transfer from a parser failure.
```python
while len(frame) < required:
    block = sock.recv(required - len(frame))
    if not block:
        raise EOFError("peer closed before full frame")
    frame.extend(block)
```
