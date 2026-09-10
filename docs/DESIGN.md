# Implementation contract

## Repository and language boundaries

`luce-server` contains only Base implementation sources (`.lucb`). Its import
namespace is `luce_server`, with public `http`, `websocket`, and `socket` modules.
`luce-http-server` is a separate Luce example and interoperability test application.
TLS remains a separate package and is outside this implementation stage.

## Ownership and concurrency

Base owns all listeners, connections, protocol parsing, buffers, upload temporary
files, static-file resolution, routing and network threads. Concurrency is bounded
and configurable. A slow client cannot allocate an unbounded number of threads or
queued application requests. Stop cancels network waits and joins server threads.

Applications receive owned request/message handles through an explicit queue.
They answer or abandon each handle; abandoning wakes its waiting connection with a
failure response. The library never invokes a Luce callback on a foreign Base
thread. Luce handlers run on Luce-owned threads and can use the same library API as
Base applications. Views returned by Base remain valid until the next documented
mutation or handle destruction; Luce's boundary copies borrowed strings and bytes.

## Delivery requirements

- HTTP/1.1 framing, persistent connections, limits and request deadlines.
- Explicit REST routing and access to request headers, path/query and body.
- Streamed uploads/downloads and descriptor-relative static mounts.
- RFC 6455 handshake, masked client frames, fragmentation, control frames and close.
- Raw TCP byte streams: applications choose their own framing.
- Bounded threaded operation, cancellation, joins and owned resource cleanup.
- A separate Luce HTTP example, native Base examples and independent socket tests.
- Native ARM64 macOS and x86-64 Linux checks, including ARC cleanup in the example.

Protocol references: [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html),
[HTTP/1.1](https://www.rfc-editor.org/rfc/rfc9112.html), and
[WebSocket](https://www.rfc-editor.org/rfc/rfc6455.html).

Implementation contracts and limits are documented in [API.md](API.md).
Executed checks and their scope belong in [VALIDATION.md](VALIDATION.md).
