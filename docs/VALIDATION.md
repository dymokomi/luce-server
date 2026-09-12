# Validation evidence

2026-09-11, ARM64 macOS, native Base compiler pinned in `bootstrap/BASE`.

`./test.sh` passes at native optimization levels 0–3. Every mode runs URL/routing
unit checks, lifecycle/startup checks and the independent Python wire suite.
Coverage includes HTTP framing/pipelining/chunking/HEAD/OPTIONS/100 Continue,
validators/ranges, a renamed static root, large uploads/downloads, overwrite
refusal, handler errors, application/read deadlines, concurrent handlers,
WebSocket fragmentation/control frames/protocol failures/close acknowledgements,
server-initiated messages, TCP streams, SIGTERM and resource cleanup.

The object rewrite adds repeated failed factories, different routes across worker
factories, constructor rejection, terminal/idempotent close, escaped request/view
expiry and an independently retained spooled body with bounded chunk reads.
A separate public-import smoke consumer (`tests/http_objects.lucb`) passed 40
concurrent requests and joined shutdown through `tests/object_smoke.py`.

`python3 tests/heap.py build/server-0` passes with zero leaked blocks/bytes for
HTTP/WebSocket, TCP and retained-body lifetimes. Native and managed ownership
runtime diagnostics are also required to be empty on normal process exit.

The separate Luce application uses this exact API and passes its own independent
native 0–3 wire matrix and macOS native/ARC heap check. Its source has no worker
attachment, recursive task startup, route identifiers or manual JSON escaping.

The standard JSON serializer has its own Base native 0–3/C comparison matrix,
checked by Python's independent decoder. It covers precise numbers, Unicode and
control escaping, snapshots, duplicate keys, malformed UTF-8, limits and ownership.

The repository workflow runs the complete native matrix on ARM64 macOS and
x86-64 Linux, using the pinned compiler. Local results above do not claim Linux
host execution; the workflow result is recorded separately after the push.

The section-seven delivery pass re-ran native optimization levels 0–3 against
Base `51a02e5` (including the ARM64 aggregate argument fix). The independent
HTTP, file, WebSocket, TCP, concurrency and shutdown suites all passed locally.
