# luce-server

A multithreaded HTTP, WebSocket, and TCP server library written entirely in
**luce-base** and compiled with its native backend. Use it to build REST services,
serve static content, and receive or send files.

The companion [luce-http-server](https://github.com/dymokomi/luce-http-server)
implements an application entirely in high-level Luce: named handler functions,
a route catalog, and a small browser demo. The server package owns protocol
processing, connection threads, buffering, and resource cleanup.

## Use the package

The repository name is `luce-server`; the source import namespace is
`luce_server`. A consumer imports:

```luce
import luce_server.http as http
```

Until the package manager exists, `tools/build.py` stages the package sources
under a consumer's source root. No server executable or compiler implementation
is embedded in the library. Dependencies and validation use full commit pins in
`bootstrap/BASE`; the companion application pins both compilers and this package.

A server lifecycle is:

1. Obtain `http.defaults()`, change its public options, and call `http.open`.
2. Register HTTP routes, WebSocket routes, and static mounts before `http.start`.
3. Start application workers. Each attaches its own `Worker` using the scalar
   `http.worker_token(server)` and calls `http.next` for owned requests.
4. Dispatch by route ID and reply once. Release each request and worker.
5. Call `http.shutdown` to drain, then close the server to join its network pool.
   Applications can opt into SIGINT/SIGTERM shutdown before starting.

Base consumers use `defer http.close_request(request)` and the corresponding
worker/server destructors. Luce maps these handles to ARC objects and supports
`with` for explicit lexical cleanup. The library never calls application code on
an unknown foreign thread. See [the public API](docs/API.md) for ownership rules,
configuration, and precise behavior.

## What it provides

- HTTP/1.1: persistent connections, pipelined input, chunked request bodies,
  `100 Continue`, body limits, absolute request/response deadlines.
- REST routing: method plus path, `{name}` parameters, decoded query values,
  automatic HEAD/OPTIONS and method-not-allowed replies.
- Static mounts: descriptor-relative file lookup, `index.html`, media types,
  HEAD, weak ETags, conditional requests and single byte ranges.
- File transfers: small bodies in bounded memory, larger bodies in temporary
  files, atomic upload publication, and buffered file downloads.
- WebSockets: explicit opening approval, fragmentation, UTF-8 validation,
  binary/text messages, ping/pong, and bounded close handshakes.
- Raw TCP: read-chunk events with application-defined framing.
- A fixed network pool, bounded application queue, cancellation, graceful
  drain, statistics, and explicit request lifetimes.

This first version uses blocking application workers over nonblocking socket
operations with deadlines. Each live connection occupies one network worker.
It does not yet provide HTTP/2, TLS, multipart parsing, an OpenAPI generator,
compression, unsolicited WebSocket broadcasts, or database integration.

## Build and test

With sibling `luce-base` and `luce-server` checkouts and a built Base compiler:

```sh
./test.sh --base ../luce-base/build/luce-base
```

The test runner builds and executes native optimization levels 0–3. Independent
Python clients exercise the actual wire protocol, files, concurrency, failures,
and shutdown. GitHub Actions runs this matrix on ARM64 macOS and x86-64 Linux.
See [validation evidence](docs/VALIDATION.md).

Build a Base consumer using the same staged package layout:

```sh
./build.sh tests/server.lucb -o build/test-server
```

For an end-user application, use the separate
[Luce example](https://github.com/dymokomi/luce-http-server).

Licensed under MIT or Apache-2.0, at your option.
