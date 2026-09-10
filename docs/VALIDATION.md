# Validation

The Base server passes native optimization levels 0–3 on ARM64 macOS and x86-64
Linux. The [validation run at `902d7ba`](https://github.com/dymokomi/luce-server/actions/runs/34540922009)
records successful native matrix steps on both hosts and a successful macOS heap
check using the compiler revision pinned in `bootstrap/BASE`.
The package is `0.1.0-dev`; this is development evidence, not a production release
or a claim that all server workloads are covered.

The independent Python clients exercise the actual native executable:

- Route precedence, decoded parameters/query values, HEAD, OPTIONS, 404/405.
- Persistent/pipelined requests, chunked bodies/trailers, 100 Continue, malformed
  framing, truncated input, body limits, and slow-request timeouts.
- Static roots that survive renaming; refusal of symlinks/FIFOs; MIME types,
  weak ETags, conditional responses and byte ranges.
- Multi-MiB file upload/download equality, atomic overwrite refusal, and cleanup
  of spooled and publication temporary files.
- Concurrent application execution, 80 parallel HTTP clients, abandoned handlers,
  late replies, bounded shutdown, and SIGTERM with an active connection.
- Fragmented UTF-8 and binary WebSockets, interleaved ping/pong, malformed frames,
  whole-message deadlines, Origin rejection, and both directions of close.
- Raw TCP byte equality across arbitrary read chunk boundaries.

The lifetime regression additionally keeps a spooled request alive after
closing its server and worker, verifies the body remains readable, rejects the
revoked token and late reply, then verifies temporary cleanup. It passes locally
and in the hosted matrix at all four native optimization levels.

`tests/unit.lucb` covers URL validation, deterministic route selection, ranges,
and locale-independent HTTP dates. `tests/server.lucb` exercises the public Base
API; the separate
[Luce application](https://github.com/dymokomi/luce-http-server) exercises ARC
handles, mutable Base options, function-valued handlers and Luce task boundaries.
Its own repository records end-to-end validation against pinned compiler/package
commits. The Base standard library's protocol codec tests and compiler gates are
additional layers; they do not replace these independent server tests.

The retained-request regression also passed the
[hosted matrix at 1fd42e1](https://github.com/dymokomi/luce-server/actions/runs/34537896033).
With Base's startup argument cleanup, `python3 tests/heap.py build/server-0`
reports zero leaked blocks/bytes for the HTTP/WebSocket, TCP, and retained-request
processes under macOS `leaks`. The hosted run above passed this check alongside
the native matrix and retains `heap.log`. This checks Base allocations in addition to the
separate application's ARC diagnostics.
