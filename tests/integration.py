#!/usr/bin/env python3
"""Exercise the real HTTP transport; every fixture owns and reaps its server."""
import argparse
import concurrent.futures
import socket
import sys
import http.client
import re
import selectors
import signal
import subprocess
import tempfile
from pathlib import Path


def run(binary):
    with tempfile.TemporaryDirectory(prefix='luce-server-') as directory:
        root = Path(directory) / 'www'
        root.mkdir()
        upload = Path(directory) / 'uploads'
        upload.mkdir()
        data = bytes(range(256)) * 1024
        (root / 'data.bin').write_bytes(data)
        (root / 'index.html').write_text('home')
        (root / 'outside').symlink_to('/etc/passwd')
        process = subprocess.Popen([str(binary), '--port', '0', '--root', str(root),
                                    '--temporary-directory', str(upload)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(15), 'server did not announce readiness'
                line = process.stdout.readline()
            match = re.search(rb':(\d+)\s*$', line)
            assert match, line
            port = int(match[1])
            if sys.platform == 'darwin':
                threads = subprocess.check_output(['ps', '-M', '-p', str(process.pid)], text=True).splitlines()[1:]
            else:
                threads = list(Path(f'/proc/{process.pid}/task').iterdir())
            assert len(threads) >= 5, f'expected coordinator and four native workers: {threads}'
            # More idle clients than one worker can hold. New requests must still
            # progress through the other workers without waiting for idle expiry.
            idle = [socket.create_connection(('127.0.0.1', port), timeout=10) for _ in range(40)]
            def concurrent_request(index):
                peer = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                try:
                    payload = bytes([index]) * 90000
                    peer.request('POST', '/echo', payload)
                    answer = peer.getresponse()
                    assert answer.status == 200 and answer.read() == payload
                finally:
                    peer.close()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                    list(executor.map(concurrent_request, range(32)))
            finally:
                for peer in idle:
                    peer.close()
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            def request(method, path, body=None, headers=None):
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            assert request('GET', '/health')[0] == 200
            assert request('POST', '/echo', data)[2] == data
            status, headers, body = request('GET', '/static/data.bin')
            assert status == 200 and body == data
            assert not list(upload.iterdir()), 'completed upload was not removed'
            assert request('HEAD', '/static/data.bin')[2] == b''
            assert request('GET', '/static/data.bin', headers={'Range': 'bytes=2-9'})[2] == data[2:10]
            assert request('GET', '/static/data.bin', headers={'If-None-Match': headers['etag']})[0] == 304
            assert request('GET', '/static/data.bin', headers={'If-Modified-Since': headers['last-modified']})[0] == 304
            assert request('GET', '/static/missing')[0] == 404
            assert request('GET', '/static/../outside')[0] == 403
            assert request('GET', '/static/outside')[0] in (403, 404)
            connection.close()
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise AssertionError('server did not stop')
            assert process.returncode == 0 and not stderr, (process.returncode, stdout, stderr)
    print('PASS live HTTP, uploads, static files, conditions, shutdown')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path, nargs='?', default=Path('build/luce-server'))
    run(parser.parse_args().binary.resolve())
