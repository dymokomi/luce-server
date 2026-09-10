# Design and delivery scope

## Code boundaries

- `src/server/http`: request framing, chunk decoding and response encoding.
- `src/server`: request/response models, route matching, validation and application lifecycle.
- `src/server/json`: bounded JSON parsing and encoding, preserving numeric precision.
- `src/server/static`: file mounts, media types, conditional responses and byte ranges.
- `src/server/base`: owned standard-library handles for sockets, files and clocks.
- `tests`: pure protocol/API checks and independent socket/client integration campaigns.

The server and application policy are Luce code. Base modules perform systems
operations and expose resources through handles; they do not contain HTTP parsing,
route selection, middleware or application handlers. Native compilation is required
for integration tests. No new C implementation is planned.

## HTTP contract

The initial protocol is HTTP/1.1, with HTTP/1.0 compatibility where explicitly
supported. Request framing follows [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html);
methods, conditions and ranges follow [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html).
Keep duplicate fields available until the field-specific interpretation is applied.
Reject conflicting framing, malformed lengths, unsupported transfer coding and
invalid line syntax before dispatch. Treat bodies as bytes, not implicitly as text.

Retain unread bytes across requests, honor persistent-connection semantics and
support chunked request bodies. Limits cover request lines, headers, body size,
connections, requests per connection and elapsed request/idle/write time.
Expect/continue handling must not wait for a body the client is waiting to send.

Response framing is computed centrally. HEAD and bodyless statuses never write
body bytes; application headers cannot override framing accidentally. A failed
response after headers have been written closes the connection rather than emitting
a second status line. Short writes advance only by confirmed bytes.

## Application and file API

Routes register explicit method/path/handler triples. Literal routes have defined
precedence over parameters; duplicate/ambiguous registration fails at setup.
Path and query conversion failures produce structured 422 responses. Missing routes
produce 404; a path with another registered method produces 405 and Allow.
Handlers return response values. Middleware and lifecycle hooks have defined order.
JSON, text, bytes, redirects and streamed files use the same response encoder.

Static mounts resolve relative paths beneath an owned directory. Decode URL escapes
once, reject invalid segments, and use descriptor-relative filesystem operations.
Do not follow symlinks outside the mount or execute served source. Serve binary
content with bounded buffers, HEAD, conditional requests and byte ranges. Uploads
must have explicit limits and cleanup on disconnect/failure.

## Concurrency and delivery gate

A nonblocking connection loop separates socket readiness from HTTP state. Synchronous
application callbacks run to completion; their execution model and blocking behavior
must be documented. Slow network peers must not block unrelated connections. Shutdown
stops accepting, drains active responses within a deadline, then closes resources.

Before release: pure parser/router/validation tests; malformed and fragmented requests;
independent HTTP client tests; pipelining, chunking and EOF; binary static files,
conditions/ranges and containment; upload/download streaming and disconnects;
concurrent bounded-resource load; shutdown; and native execution on both supported hosts.
Tests must check ARC cleanup as well as response bytes. TLS integration has a separate gate.
