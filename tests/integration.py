#!/usr/bin/env python3
"""Independent HTTP, WebSocket and TCP clients exercise the Base server package."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import email.utils
import http.client
import os
from pathlib import Path
import select
import queue
import threading
import signal
import sys
import socket
import struct
import subprocess
import tempfile
import time


def startup_line(process):
    if os.name != 'nt':
        ready, _, _ = select.select([process.stdout], [], [], 15)
        assert ready, 'application startup timed out'
        return process.stdout.readline()
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        return lines.get(timeout=15)
    except queue.Empty:
        raise AssertionError('application startup timed out') from None


def request_shutdown(process_id, console_close=False):
    if os.name != 'nt':
        os.kill(process_id, signal.SIGTERM)
        return
    # The server owns a hidden console. A short-lived helper attaches to that
    # console to deliver a real CTRL_BREAK event without signaling the test host.
    helper = r"""
import ctypes, sys, time
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint32)
handler = handler_type(lambda event: 1)
kernel.GetConsoleWindow.restype = ctypes.c_void_p
kernel.FreeConsole()
assert kernel.AttachConsole(int(sys.argv[1])), ctypes.get_last_error()
assert kernel.SetConsoleCtrlHandler(handler, True), ctypes.get_last_error()
if sys.argv[2] == 'close':
    window = kernel.GetConsoleWindow()
    assert window, ctypes.get_last_error()
    kernel.FreeConsole()
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    assert user.PostMessageW(window, 0x0010, 0, 0), ctypes.get_last_error()  # WM_CLOSE
    raise SystemExit(0)
assert kernel.GenerateConsoleCtrlEvent(1, 0), ctypes.get_last_error()
time.sleep(.1)
kernel.FreeConsole()
"""
    subprocess.run([sys.executable, '-c', helper, str(process_id), 'close' if console_close else 'break'],
                   check=True, timeout=5)


def eventually(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "asynchronous cleanup did not finish"


def finish_process(process, timeout):
    """Collect output until the owned process exits, without waiting on inherited pipes.

    macOS diagnostic helpers can inherit a pipe and outlive leaks itself. The
    exit status and all bytes already written still belong to this test process.
    """
    streams = (process.stdout, process.stderr)
    chunks = ([], [])
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
    deadline = time.monotonic() + timeout
    while True:
        for stream, output in zip(streams, chunks):
            data = stream.read1(65536)
            if data:
                output.append(data)
        if process.poll() is not None:
            for stream, output in zip(streams, chunks):
                while data := stream.read1(65536):
                    output.append(data)
            return tuple(b''.join(output) for output in chunks)
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(process.args, timeout,
                output=b''.join(chunks[0]), stderr=b''.join(chunks[1]))
        time.sleep(.01)


def response(stream, head=False):
    line = stream.readline()
    assert line.startswith(b"HTTP/1."), line
    status = int(line.split()[1])
    fields = {}
    while True:
        line = stream.readline()
        assert line, "EOF inside HTTP fields"
        if line == b"\r\n":
            break
        name, value = line.split(b":", 1)
        fields[name.lower()] = value.strip()
    size = 0 if head or status < 200 or status in (204, 304) else int(fields.get(b"content-length", 0))
    data = stream.read(size)
    assert len(data) == size, (len(data), size)
    return status, fields, data


def exact(stream, size):
    data = stream.read(size)
    assert len(data) == size, (len(data), size)
    return data


def frame(opcode, data=b"", final=True, masked=True):
    first = opcode | (0x80 if final else 0)
    bit = 0x80 if masked else 0
    size = len(data)
    if size < 126:
        header = bytes((first, bit | size))
    elif size < 65536:
        header = bytes((first, bit | 126)) + struct.pack("!H", size)
    else:
        header = bytes((first, bit | 127)) + struct.pack("!Q", size)
    if not masked:
        return header + data
    mask = os.urandom(4)
    return header + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))


def read_frame(stream):
    first, second = exact(stream, 2)
    assert not second & 0x80, "server frames must not be masked"
    size = second & 0x7f
    if size == 126:
        size = struct.unpack("!H", exact(stream, 2))[0]
    elif size == 127:
        size = struct.unpack("!Q", exact(stream, 8))[0]
    return first & 15, exact(stream, size)


class Server:
    def __init__(self, binary, root, uploads, raw=False, mode=None):
        launch = {}
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            launch = dict(creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        self.process = subprocess.Popen([str(binary), str(root), str(uploads), mode or ("raw" if raw else "http")],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, **launch)
        try:
            line = startup_line(self.process)
        except BaseException:
            self.process.kill()
            self.process.communicate()
            raise
        assert line.startswith(b"READY "), (line, self.process.poll())
        self.port = int(line.split()[1])

    def connect(self):
        return socket.create_connection(("127.0.0.1", self.port), timeout=4)

    def request(self, method, path, data=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        try:
            client.request(method, path, body=data, headers=headers or {})
            reply = client.getresponse()
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            client.close()

    def websocket(self, path="/ws"):
        peer = self.connect()
        stream = peer.makefile("rb")
        key = base64.b64encode(os.urandom(16))
        peer.sendall(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\n"
                     b"Upgrade: websocket\r\nSec-WebSocket-Version: 13\r\n"
                     b"Sec-WebSocket-Key: " + key + b"\r\n\r\n")
        status, fields, body = response(stream)
        expected = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        assert status == 101 and fields[b"sec-websocket-accept"] == expected and not body
        return peer, stream

    def finish(self, console_close=False):
        output, errors = self.process.communicate(timeout=6)
        # A close notification may let main return or let Windows terminate after
        # acknowledgement. In either case every worker must finish before STOPPED.
        allowed = (0, 0xC000013A) if console_close else (0,)
        assert self.process.returncode in allowed and not errors and output == b"STOPPED\n", (
            self.process.returncode, output, errors)

    def cleanup(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.communicate()


def http_tests(binary, directory):
    root = directory / "public"
    root.mkdir()
    uploads = directory / "uploads"
    uploads.mkdir()
    (root / "index.html").write_bytes(b"<h1>native Base server</h1>")
    (root / "data.txt").write_bytes(b"0123456789")
    (root / "nested").mkdir()
    (root / "nested/file.txt").write_bytes(b"nested")
    (root / "outside").symlink_to(uploads, target_is_directory=True)
    (root / "link.txt").symlink_to("data.txt")
    if os.name != "nt":
        os.mkfifo(root / "pipe")
    else:
        print("SKIP Unix FIFO entry: Windows has no filesystem FIFO nodes", flush=True)
    server = Server(binary, root, uploads)
    try:
        assert server.request("GET", "/ping")[2] == b'{"ok":true}'
        assert server.request("GET", "/items/caf%C3%A9")[2] == "café".encode()
        assert server.request("GET", "/query?name=one+two")[2] == b"one two"
        assert server.request("GET", "/query?name=%ff")[0] == 500
        assert server.request("POST", "/items/7")[0] == 405
        status, headers, body = server.request("OPTIONS", "/items/7")
        assert status == 204 and not body and "HEAD" in headers["Allow"]
        assert server.request("GET", "/missing")[0] == 404
        for path in ("/static/../uploads/file", "/static/%2e%2e/file", "/static/a%2fb", "/static/%00", "/static//file"):
            assert server.request("GET", path)[0] == 400, path
        for path in ("/static/outside/file", "/static/link.txt", "/static/pipe"):
            assert server.request("GET", path)[0] == 404, path
        assert server.request("GET", "/static/")[2] == (root / "index.html").read_bytes()
        assert server.request("GET", "/static/nested/file.txt")[2] == b"nested"
        status, headers, body = server.request("GET", "/static/data.txt")
        assert status == 200 and body == b"0123456789"
        assert headers["Content-Type"].startswith("text/plain")
        assert abs(email.utils.parsedate_to_datetime(headers["Date"]).timestamp() - time.time()) < 10
        assert server.request("HEAD", "/static/data.txt")[2] == b""
        assert server.request("GET", "/static/data.txt", headers={"If-None-Match": headers["ETag"]})[0] == 304
        assert server.request("GET", "/static/data.txt", headers={"Range": "bytes=2-5"})[2] == b"2345"
        assert server.request("GET", "/static/data.txt", headers={"Range": "bytes=-3"})[2] == b"789"
        assert server.request("GET", "/static/data.txt", headers={"Range": "bytes=99-"})[0] == 416
        assert server.request("GET", "/static/data.txt", headers={"Range": "bytes=2-5", "If-Range": '"different"'})[0] == 200
        assert server.request("GET", "/static/data.txt", headers={"If-Match": headers["ETag"]})[0] == 412
        moved = directory / "moved-public"
        root.rename(moved)
        assert server.request("GET", "/static/nested/file.txt")[2] == b"nested"

        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"GET /ping HTTP/1.1\r\nHost: localhost\r\n\r\n"
                         b"HEAD /ping HTTP/1.1\r\nHost: localhost\r\n\r\n"
                         b"GET /items/42 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            assert response(stream)[2] == b'{"ok":true}'
            assert response(stream, head=True)[1][b"content-length"] == b"11"
            assert response(stream)[2] == b"42"
            assert stream.read() == b""
        for wire, close_code in (
                (frame(1, b"unmasked", masked=False), 1002),
                (frame(1, b"\xff"), 1007),
                (b"\x89\xfe\x00\x7e", 1002)):
            peer, stream = server.websocket()
            with peer, stream:
                peer.sendall(wire)
                opcode, payload = read_frame(stream)
                assert opcode == 8 and struct.unpack("!H", payload[:2])[0] == close_code

        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"POST /echo HTTP/1.1\r\nHost: localhost\r\nContent-Length: 5\r\nExpect: 100-continue\r\n\r\n")
            assert response(stream)[0] == 100
            peer.sendall(b"hello")
            assert response(stream)[2] == b"hello"

        with server.connect() as peer, peer.makefile("rb") as stream:
            request = (b"POST /echo HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"
                       b"3;name=value\r\nabc\r\n2\r\nde\r\n0\r\nX-Checksum: okay\r\n\r\n"
                       b"GET /ping HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            for offset in range(0, len(request), 3):
                peer.sendall(request[offset:offset + 3])
            assert response(stream)[2] == b"abcde"
            assert response(stream)[0] == 200

        for malformed in (
                b"GET /ping HTTP/1.1\r\nHost: a\r\nHost: b\r\n\r\n",
                b"POST /echo HTTP/1.1\r\nHost: a\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\n",
                b"POST /echo HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\nx\r\n"):
            with server.connect() as peer, peer.makefile("rb") as stream:
                peer.sendall(malformed)
                assert response(stream)[0] == 400
        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"POST /echo HTTP/1.1\r\nHost: a\r\nContent-Length: 9000000\r\n\r\n")
            assert response(stream)[0] == 413
        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"POST /echo HTTP/1.1\r\nHost: a\r\nContent-Length: 10\r\n\r\nabc")
            peer.shutdown(socket.SHUT_WR)
            assert response(stream)[0] in (400, 500)
        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"GET /ping HTTP/1.1\r\nHost:")
            assert response(stream)[0] == 408

        payload = bytes(range(256)) * 8192
        assert server.request("PUT", "/upload/payload.bin", payload)[0] == 201
        assert (uploads / "payload.bin").read_bytes() == payload
        assert server.request("GET", "/files/payload.bin")[2] == payload
        assert server.request("PUT", "/upload/payload.bin", b"replacement")[0] == 500
        assert (uploads / "payload.bin").read_bytes() == payload
        eventually(lambda: not list(uploads.glob(".luce-*")))
        assert server.request("POST", "/failure", b"")[0] == 500
        assert server.request("GET", "/slow")[0] == 503
        time.sleep(0.55)  # allow the deliberately late application handler to exit
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: server.request("GET", "/parallel"), range(2)))
        assert max(int(result[2]) for result in results) >= 2
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: server.request("GET", "/ping"), range(80)))
        assert all(status == 200 and body == b'{"ok":true}' for status, _, body in results)

        peer, stream = server.websocket("/ws/greeting")
        with peer, stream:
            assert read_frame(stream) == (1, b"hello before input")
            peer.sendall(frame(8, struct.pack("!H", 1000)))
            assert read_frame(stream) == (8, struct.pack("!H", 1000))
        peer, stream = server.websocket()
        with peer, stream:
            peer.sendall(frame(1, b"close"))
            assert read_frame(stream) == (1, b"close")
            assert read_frame(stream) == (8, struct.pack("!H", 1000))
            # The server must give the peer time to acknowledge its close.
            assert not select.select([peer], [], [], 0.05)[0]
            peer.sendall(frame(8, struct.pack("!H", 1000)))
            assert stream.read() == b""
        peer, stream = server.websocket()
        with peer, stream:
            # Continuations make progress inside the idle timeout, but the
            # complete message still has one absolute request deadline.
            peer.sendall(frame(1, b"start", final=False))
            time.sleep(0.4)
            peer.sendall(frame(0, b"middle", final=False))
            opcode, payload = read_frame(stream)
            assert opcode == 8 and struct.unpack("!H", payload[:2])[0] == 1001
        peer, stream = server.websocket()
        with peer, stream:
            euro = "hello €".encode()
            peer.sendall(frame(1, euro[:-1], final=False) + frame(9, b"ping") + frame(0, euro[-1:]))
            assert read_frame(stream) == (10, b"ping")
            assert read_frame(stream) == (1, euro)
            large = os.urandom(100000)
            peer.sendall(frame(2, large))
            assert read_frame(stream) == (2, large)
            peer.sendall(frame(8, struct.pack("!H", 1000)))
            assert read_frame(stream) == (8, struct.pack("!H", 1000))
            assert stream.read() == b""
        with server.connect() as peer, peer.makefile("rb") as stream:
            peer.sendall(b"GET /ws HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                         b"Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                         b"Origin: http://blocked.test\r\n\r\n")
            assert response(stream)[0] == 403
        assert server.request("POST", "/shutdown", b"")[2] == b"bye"
        server.finish()
        assert not list(uploads.glob(".luce-*"))
    finally:
        server.cleanup()


def tcp_tests(binary, directory):
    server = Server(binary, directory, directory, raw=True)
    try:
        with server.connect() as peer, peer.makefile("rb") as stream:
            payload = os.urandom(100000)
            peer.sendall(payload)
            assert exact(stream, len(payload)) == payload
            peer.sendall(b"stop")
            assert exact(stream, 4) == b"stop"
        server.finish()
    finally:
        server.cleanup()


def signal_tests(binary, directory, console_close=False):
    server = Server(binary, directory, directory, raw=True)
    try:
        peer = server.connect()
        try:
            peer.sendall(b"hello")
            assert peer.recv(5) == b"hello"
            request_shutdown(server.process.pid, console_close=console_close)
            server.finish(console_close=console_close)
        finally:
            peer.close()
    finally:
        server.cleanup()


def lifetime_tests(binary, directory):
    server = Server(binary, directory, directory, mode="lifetime")
    try:
        assert server.request("POST", "/retain", b"retained payload")[2] == b"retained"
        assert server.request("POST", "/shutdown", b"")[2] == b"bye"
        # The fixture checks expiry and retained body contents during worker disposal.
        server.finish()
        assert not list(directory.glob(".luce-*"))
    finally:
        server.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="luce-server-tests-") as temporary:
        directory = Path(temporary)
        http_tests(arguments.binary.resolve(), directory)
        tcp_tests(arguments.binary.resolve(), directory)
        signal_tests(arguments.binary.resolve(), directory)
        if os.name == 'nt':
            signal_tests(arguments.binary.resolve(), directory, console_close=True)
        lifetime_tests(arguments.binary.resolve(), directory)
    print("PASS independent HTTP, file, WebSocket, TCP, concurrency and shutdown checks")
