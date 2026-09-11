# Server API

`http`, `websocket` and `socket` are public module exports. All implementations
are Base structs. Luce constructs them with `Type(...)`, owns them through ARC and
calls their methods. Base callers explicitly close direct objects and release
owning `interop.Reference`/callback carriers. Copies of Base carriers borrow.

## Server and configuration

`ServerConfig` contains address/port, network/application worker counts, backlog,
request/idle/response/application/shutdown deadlines, body/memory/response limits,
requests per connection and temporary directory. Durations are milliseconds and
sizes are bytes. The address is numeric IPv4/IPv6; port zero selects a free port.
Defaults are 8 network workers, 2 application workers, a 64 MiB body limit, a
64 KiB memory body threshold and a 1 MiB response limit. Validation occurs before
resource acquisition.

`Server(config, factory, application_data = "")` copies configuration. The named
factory receives a copied string on each worker and returns `Application`, the
retained callable returned by `Router.application()`. It can capture state created
on that worker. Route declarations must agree across workers, including mounted
static-root identity. A mismatch fails startup and joins every started worker.

| Method | Behavior |
| --- | --- |
| `mount(prefix, StaticRoot)` | Register an owned static directory before startup |
| `shutdown_on_signals()` | Opt into process SIGINT/SIGTERM before startup |
| `start()` | Bind and start both bounded pools; return only when factories are ready |
| `port()` | Query the assigned listener port |
| `run()` | Start if necessary, then wait for shutdown and join |
| `shutdown()` | Stop accepting and begin a bounded graceful drain |
| `statistics()` | Read connection, active, completed HTTP, error and outstanding-work counters |
| `close()` | Cancel/join and release resources; terminal and idempotent |

Signal handlers are restored after the last subscribing server closes. Shutdown
cancels blocked IO after the configured drain deadline. A WebSocket close permits
an additional bounded one-second peer acknowledgement. Application code must
return from CPU work cooperatively; arbitrary user code is not forcibly killed.

## Routing and responses

`Router()` owns worker-local handlers. `add(Route(method, pattern, handler))`
registers any uppercase method; `get`, `post` and `put` are conveniences.
`websocket(pattern, handler)` registers a session opening. `socket(handler)` selects
one TCP stream handler, mutually exclusive with HTTP routes. `mount(prefix, root)`
registers a worker-local static declaration. `application()` freezes the router and
returns its retained dispatch callable. Main-thread `Server.mount` is convenient
for shared static roots. API routes take precedence over broad static mounts.

Patterns match decoded path segments; `{name}` captures one segment. Literal routes
outrank parameter routes. GET supports HEAD fallback; registered paths receive
OPTIONS/Allow and method-not-allowed replies when appropriate.

HTTP handlers return `Response`. Construction accepts text and status (default
200). Static constructors `bytes`, `json` and `file` select body representation.
`json` accepts a standard `json.Value`, never an unchecked JSON fragment. Methods
`header`, `shutdown_after` and `close_connection` edit the uncommitted response.
Framing headers are owned by the server. A response commits once; reuse or later
mutation fails. A handler failure becomes a 500 response. Application deadlines
expire requests and produce 503; a late returned response is discarded safely.

`Request` is a checked view. `method`, `path`, `header`/`header_bytes`, `parameter`,
`integer_parameter`, `query` and `integer_query` provide typed access. Header text
and decoded query text validate UTF-8. Returned native text views are borrowed;
Luce copies them. Calling an escaped request or bound method after its handler
returns fails before accessing its storage.

`request.body()` returns an owned `Body` independent of the request. `size` reports
bytes; `bytes(limit)`/`text(limit)` perform explicit bounded loads. `read(maximum)`
reads successive chunks (default 32 KiB), and `rewind` resets that cursor. Native
read views last until the next read/mutation; Luce copies them. `save(path,
replace = false)` publishes through a temporary sibling after the full copy.
Bodies over the memory threshold own temporary files, deleted on release. Paths
are application policy; decoded route parameters are not interpreted as paths by
the library. `Response.file` opens and retains a regular file for bounded transfer.

`StaticRoot(path)` owns an opened root. Mounts duplicate its descriptor, so closing
a declaration or renaming the root does not invalidate mounted content. Serving
uses relative directory descriptors and regular-file checks. It supports index.html,
HEAD, weak ETags, one byte range and relevant preconditions. No directory listing
is generated.

## Sessions

`websocket.Session` is a checked handler-scope view. `header` inspects the opening.
`accept(protocol = "")` validates the handshake and optional offered subprotocol;
`reject(Response)` answers before upgrading. The application decides Origin and
identity policy. `receive()` returns an owned `Message` or none after closure.
Messages expose `is_text`, `body`, `bytes` and `text`. `send(message)`, `send_text`
and `send_bytes` support replies and server-initiated traffic. Fragmentation,
masking checks, ping/pong, UTF-8 validation and protocol-close codes are internal.
`close(code = 1000)` performs a bounded close handshake. Returning without accepting
rejects the opening. Owned messages may outlive the scoped session.

`socket.Session` exposes `read(maximum = 16384)`, `write(bytes)`, `close` and
`shutdown_server`. Read boundaries have no message meaning; an empty read denotes
EOF. A session may write before reading. Socket/session operations stay on their
application runtime thread and use native cancellation/deadline primitives.

HTTP bodies, responses and message snapshots can be retained on their runtime
thread. Request/session views cannot extend validity by being retained. No callback
or ARC owner crosses a worker boundary.
