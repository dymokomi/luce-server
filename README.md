# luce-server

An HTTP application and file server written in Luce. The API follows the explicit
parts of FastAPI's model: registered handlers, typed path/query/body validation,
structured responses, middleware and documented routes. Luce's own syntax and type
system determine how these are expressed.

Implementation is in progress. The initial target is HTTP/1.1 with nonblocking
connections, bounded request handling, streamed files and graceful shutdown on
ARM64 macOS and x86-64 Linux. TLS is a separate, paused package; the transport
boundary allows it to be integrated later.

HTTP parsing, routing, application behavior and file-serving policy live in Luce.
Small Base modules expose the standard library's sockets, files and clocks through
owned handles. Builds use the native compiler backend.

See [design and delivery scope](docs/DESIGN.md). There is no server release yet.
