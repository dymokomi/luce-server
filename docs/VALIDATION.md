# Implementation status

The initial Base implementation passes local native checks on ARM64 macOS.
`tests/unit.lucb` covers URL decoding and deterministic routing;
`tests/integration.py` uses independent Python HTTP/WebSocket/TCP clients against
`tests/server.lucb` and verifies routing, pipeline boundaries, chunked input,
static mounts, byte ranges, upload/download streaming, temporary cleanup,
concurrent application workers, handler abandonment/timeouts, and shutdown.

The directory-relative file primitive is pinned in `bootstrap/BASE`.
The complete optimization matrix, hosted Linux/macOS gate, and downstream Luce
application remain in progress. This is not yet a release verification record.
