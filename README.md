# luce-server

A multithreaded server library written entirely in **Luce Base**. It provides HTTP
routing, REST responses, static content, bounded file transfers, WebSocket sessions
and TCP streams. The library owns its network/application workers and shutdown.
Applications declare their behavior through ordinary structs, methods and callbacks.

The separate [luce-http-server](https://github.com/dymokomi/luce-http-server) project
shows the API from high-level Luce. Its route factory has this shape:

```luce
from http import Router, Application
from api import Api

pub func configure(upload_directory: str) -> Application!:
    let api = Api(upload_directory)
    let router = Router()
    router.get("/api/health", api.health)
    router.put("/api/files/{name}", api.upload)
    router.websocket("/ws/echo", api.websocket_echo)
    return router.application()
```

The named factory constructs worker-local handlers. A main function constructs
`Server(ServerConfig(...), configure, application_data)`, optionally mounts a
`StaticRoot`, and calls `start()`/`run()`. No application code schedules threads,
attaches worker tokens or dispatches route identifiers.

HTTP handlers take a checked `Request` and return a `Response`. `Response.json`
uses structured standard `json.Value` objects; `Response.file` owns an opened file.
`request.body()` returns an independently owned `Body`, with bounded reads and
atomic file publication. A retained request view expires when its handler returns.

A WebSocket handler accepts or rejects its opening, then uses `receive`, `send`,
`send_text`, `send_bytes` and `close`. It can send before receiving any message.
TCP handlers use `read`/`write` on a byte stream, with explicit application framing.
Both kinds of session occupy an application worker for their lifetime. Configure
worker counts for the desired number of concurrent handlers/sessions; all pools
and queues are bounded.

Public modules are `http`, `websocket` and `socket`. A consumer's `luce.toml` uses:

```toml
[dependencies]
luce_server = "../luce-server"
```

Imports resolve through the package's actual exports. Native compilation is the
default. The Base compiler pin is in `bootstrap/BASE`. JSON is a separate package:
check out sibling `luce-json` at `bootstrap/JSON` before building/testing. The test
builder verifies that revision and copies both packages into its isolated source
tree; tests importing JSON directly declare that dependency too.
A complete Base consumer is
in [tests/server.lucb](tests/server.lucb); it uses explicit Base reference ownership.

```sh
./test.sh
```

The gate runs native optimization levels 0–3 with independent Python HTTP,
WebSocket and TCP clients. It covers routing, HEAD/OPTIONS, keep-alive, pipelining,
chunking, `100 Continue`, static validators/ranges, uploads, slow peers, application
errors/deadlines, concurrent handlers, expired views, retained spooled bodies,
startup failures and joined shutdown. On macOS:

```sh
python3 tests/heap.py build/server-0
```

See [API](docs/API.md), [design](docs/DESIGN.md) and
[validation evidence](docs/VALIDATION.md). TLS, HTTP/2, multipart parsing and
database integration remain separate work. Licensed under MIT or Apache-2.0.

## Windows x64

Build sibling `luce-base` checkouts with `python tools/build_windows.py` in each compiler repository. Run `python tests/run.py` in this repository; the runner selects the sibling Windows executables.
Windows shutdown uses console control events. The integration runner gives its server a private console and verifies graceful Ctrl+Break shutdown. Temporary storage defaults to the host temporary directory.
