# Public API and contracts

Import `luce_server.http`. Base may additionally use the convenience modules
`luce_server.websocket` and `luce_server.socket`. All implementation is Base;
Python and shell are used only for builds and independent tests.

## Configuration and lifetime

`defaults() -> Options` returns mutable configuration. `open(options) -> Server!`
binds the listener, validates limits, and retains owned copies of strings.
Register routes and mounts before `start(server)`. Reconfiguration and a second
start fail. Port zero requests an OS-assigned port; `port(server)` returns it.
The address is numeric IPv4/IPv6; name resolution is the application's choice.

| Option | Default | Meaning |
| --- | --- | --- |
| address / port | 127.0.0.1 / 8080 | Listener endpoint |
| network_threads | 8 | Fixed connection workers, allowed 1–64 |
| backlog | 128 | OS listener backlog |
| request_timeout_ms | 30000 | Complete HTTP request or WebSocket message |
| idle_timeout_ms | 5000 | Wait for the next request/message/chunk |
| response_timeout_ms | 30000 | Complete outbound response |
| application_timeout_ms | 30000 | Queue plus handler reply wait |
| shutdown_timeout_ms | 5000 | Drain before canceling remaining connections |
| body_limit | 64 MiB | Complete request/message size, at most 1 GiB |
| memory_body_limit | 64 KiB | Spill threshold, at most body_limit |
| response_limit | 1 MiB | Buffered response size, at most 64 MiB |
| requests_per_connection | 100 | HTTP keep-alive request cap |
| temporary_directory | /tmp | Existing directory for spooled bodies |

All deadlines use monotonic time. Timeouts must be 1–3,600,000 milliseconds.
Route/mount registration is capped at 128 entries; headers and connection input
have fixed bounds. The queue has 64 entries and retained requests are capped at
four times `network_threads`. Connections beyond the network pool wait in the
OS backlog. Pool sizes are explicit capacity choices, not unlimited concurrency.

`worker_token(server) -> i64!` is an opaque registration token, available after
start. Each application thread calls `attach(token) -> Worker!` for its own
handle, then `next(worker) -> Request?`. None means shutdown. A token can cross
Luce task boundaries; a handle must stay on its owning application thread.
Closing the server revokes its token. The token cannot be used as a pointer.

`Server`, `Worker`, and `Request` own references. Base must close each exactly
once. Do not use a closed handle or concurrently call methods on a single
application handle. Closing an unanswered request abandons it, waking its
connection with 503. A queued or running handler that misses its deadline also
produces 503; a later reply fails with `request_closed`. Application code cannot
be forcibly stopped, so callers must arrange for their own handlers to return.

The server retains shared state until the last outstanding worker/request is
released. `close_server` cancels and joins network threads; it does not destroy
an application-owned handle behind its owner's back. Base borrowed strings and
bytes remain valid until their documented mutation or request destruction.
Luce's interop wrappers copy them into ARC values.

## Routing and requests

`route(server, method, pattern, id)` registers an uppercase method and origin-form
path. Patterns have literal segments or whole-segment `{name}` parameters. A
literal route wins over a parameter route for the same method; remaining ties
use registration order. Explicit HEAD routes precede GET fallback. Trailing
slashes are significant. Wildcards and regex routing are not implemented.

An API path owns automatic OPTIONS/405 behavior even beneath a static mount.
Unknown paths return 404. Protocol/path errors return 400, oversized bodies 413,
request timeouts 408, and unavailable/expired application dispatch 503.

| Function | Result / behavior |
| --- | --- |
| route_id(request) | Application's registered integer ID |
| method / path | Method and decoded path |
| parameter(request, name) | Optional decoded route segment |
| query(request, name) | First matching decoded query value; fallible |
| header(request, name) | First field, UTF-8 validated; optional and fallible |
| header_bytes(request, name) | First raw field bytes; optional |
| body_size(request) | Received byte count |
| body_bytes(request, limit) | Explicit bounded in-memory view |
| body_text(request, limit) | Same, with UTF-8 validation |
| save_body(request, destination, replace) | Atomic publication of the received body |

Malformed percent escapes, controls, invalid UTF-8, dot segments, repeated path
separators, and encoded path separators are rejected. A query view expires on the
next query call; a body view expires on the next body read. Missing names return
none. These accessors are for HTTP and WebSocket events; raw TCP has only body
accessors. Bodies are completely received before dispatch, spilling to disk
above the configured memory threshold. This is bounded streaming storage, not
an application callback for each incoming HTTP chunk.

## Replies and files

Set optional `response_header(request, name, value)` fields before committing a
reply. The server owns framing, connection, Date and Content-Type fields. Header
names/values are validated and the total field count/size is bounded.

- `reply(request, status, content_type, bytes)` copies a bounded response.
- `text(request, status, value)` selects UTF-8 plain text.
- `json(request, status, value)` selects JSON; the caller supplies serialized JSON.
- `reply_file(request, filename)` streams an opened regular file with its MIME type.

Exactly one successful reply commits an event. HTTP HEAD omits body bytes while
retaining the representation length; 204/304 suppress bodies. Files are streamed
in fixed blocks and a truncated/unreadable file closes the connection rather
than appending a second HTTP response. File paths passed by an application are
its policy; they are not automatically confined to a mount.

`save_body` writes a temporary sibling, then publishes the complete file. With
`replace = false`, an existing destination fails without overwriting it. This
provides atomic visibility, not a promise of crash durability. Public error
aliases are `invalid_request`, `limit_exceeded`, `request_closed`, `invalid_state`,
`file_missing`, and `file_exists`; other standard I/O failures propagate.

`static_files(server, prefix, directory)` keeps the root directory open. Every
path component is opened relative to that root without following symlinks;
only regular files are served. Mount identity survives renaming the root.
Directories requested with a trailing slash use `index.html`; there is no
listing or general directory redirect. Mount prefixes select the longest match.
Files support GET/HEAD, weak metadata ETags, If-None-Match, If-Match existence
checks, and single byte ranges. Multiple ranges are ignored. Weak validators
cannot satisfy If-Range, so such requests receive the complete representation.
Last-Modified/If-Modified-Since and multipart ranges are not implemented.

## WebSocket and TCP

`websocket_route(server, pattern, id)` registers an HTTP upgrade endpoint. Its
first event satisfies `is_websocket_open`. Inspect headers and either send an
HTTP rejection or call `accept_websocket(request, protocol)`. The selected
subprotocol must have been offered; the empty string selects none. Origin and
identity policy belong to the application.

Subsequent events contain complete text/binary messages; `is_text_message`
distinguishes them. `send_message` replies with the same message kind, validating
outgoing text. Base's `websocket.route/accept/send` are convenience wrappers.
Fragments and control frames are handled by Base; interleaved ping/pong does not
reset the complete-message deadline. A server-initiated close waits at most one
second for its peer. Messages are dispatched serially within a connection;
there is no unsolicited push/broadcast API in this version. A busy application
handler delays further reads (including ping) until it answers or times out.

`socket.open(options)` creates a raw TCP listener using the same worker model.
Each request contains one read chunk of at most 16 KiB. `socket.send` sends the
reply bytes. Chunk boundaries are arbitrary: applications own record framing.

## Shutdown and observation

`shutdown(server)` begins a bounded drain: stop accepting new connections,
finish current replies, then cancel survivors. `shutdown_after_reply(request)`
and `close_after_reply(request)` set policies before committing that reply.
`close_server` performs immediate cancellation/join and final ownership release.
Closing HTTP/TCP peers and closing WebSockets unblock connection workers.

`shutdown_on_signals(server)` opts into process-wide SIGINT/SIGTERM handlers;
register it before start. The handlers only advance an atomic generation counter;
the server's clock thread starts the drain. Previous handlers are restored when
the last subscribing server closes. Do not independently replace these handlers
while subscribers are active. A bounded close handshake may add up to one second
to a WebSocket worker's final cleanup.

`statistics(server)` returns observational counters for connections, active
connections, completed application/static requests, failures, and outstanding
requests. These independently sampled counters are not a transactional snapshot
or a complete HTTP access log.
