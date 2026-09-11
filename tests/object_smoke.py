#!/usr/bin/env python3
"""Exercise a real object-API listener and worker runtime with independent HTTP."""
import concurrent.futures
import http.client
from pathlib import Path
import subprocess
import sys

binary = Path(sys.argv[1]).resolve()
process = subprocess.Popen([binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    ready = process.stdout.readline().strip()
    assert ready.startswith('READY '), (ready, process.communicate(timeout=10))
    port = int(ready.split()[1])
    def request(index):
        client = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            client.request('GET', '/ping')
            response = client.getresponse()
            assert response.status == 200 and response.read() == b'pong'
        finally:
            client.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(request, range(40)))
    process.terminate()
    output, errors = process.communicate(timeout=10)
    assert process.returncode == 0 and output == 'STOPPED\n' and not errors, (process.returncode, output, errors)
finally:
    if process.poll() is None:
        process.kill()
        process.communicate()
print('PASS object API, retained handlers, parallel requests and joined shutdown')
