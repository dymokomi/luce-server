# luce-server

A universal server library written entirely in **luce-base**, compiled natively.
HTTP, WebSocket and raw TCP transports share bounded concurrency and resource
ownership. Applications can provide REST routes, receive and send files, and mount
static content. `luce-http-server` is a separate Luce application exercising the
library boundary.

This is a fresh implementation. The earlier Luce server was retired; its source is
available only in Git history. See [the implementation contract](docs/DESIGN.md).
