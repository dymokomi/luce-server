# Design

`server` owns lifecycle and validated configuration. `router` owns each worker's
route callbacks and invokes them on that runtime. Public modules export types;
request, response, body, static root and protocol sessions have separate owners.

`internal/model` contains neutral layouts only: server configuration, lifecycle,
dispatch synchronization, counters, exchange bookkeeping and optional HTTP storage.
A TCP exchange has no HTTP request allocation. `lifecycle`, `application_pool`,
`pool`, `dispatch_queue`, `request_state` and `shutdown` implement their respective
resource obligations without circular module dependencies. The sole teardown
coordinator cancels transport/queues, joins network and application threads, drains
queued references, then releases the listener and state.

The network pool accepts a fixed number of simultaneous connections. HTTP parsing
and ordered wire responses remain on a network worker. A bounded queue transfers a
neutral exchange reference to an application worker. `interop.Worker` creates that
worker's runtime, invokes the named factory and keeps its returned router callback
on the same thread until shutdown. Transport never invokes a managed callback.

HTTP request storage is retained through application scope even after a timeout.
The scope's lease invalidates before release. `Body` can take ownership of its
received storage, independent of request validity. A returned response transfers
neutral buffers/file ownership under the dispatch lock exactly once; late replies
fail before transfer. The network sees immutable response storage after commitment.

A WebSocket/TCP exchange parks its network worker while its application callback
owns protocol IO. Its heap-backed connection/input stay alive until the handler
returns, including cancellation. Separate session implementations handle whole
WebSocket messages and TCP streams. Both use standard nonblocking deadline streams;
there are no request-shaped TCP chunks or message event identifiers.

Limits are independent: OS backlog, fixed pools, bounded queue, request header/path,
in-memory body threshold, total body, response, per-connection request count and
absolute deadlines. Uploads spool instead of growing memory with file size. Signal
handling is opt-in and shared registrations restore previous process handlers.

The initial synchronous session API occupies a worker for each live session. It
provides bounded concurrency, not an async multiplexing runtime. TLS, HTTP/2 and a
larger event-driven session scheduler are separate designs.
