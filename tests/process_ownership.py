#!/usr/bin/env python3
"""A fixture must reap helpers even when their parent has already exited."""
import fcntl
from pathlib import Path
import shlex
import sys
import tempfile
import time

from integration import Server


with tempfile.TemporaryDirectory(prefix='luce-server-process-owner-') as temporary:
    work = Path(temporary)
    child = work / 'child.py'
    child.write_text('''import fcntl, sys, time
with open(sys.argv[1], 'w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    print('LOCKED', flush=True)
    time.sleep(60)
''')
    parent = work / 'parent.py'
    parent.write_text('''import subprocess, sys
child = subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]],
                         stdout=subprocess.PIPE, text=True)
assert child.stdout.readline() == 'LOCKED\\n'
print('READY 0', flush=True)
# The helper remains alive, holding its lock and the inherited stderr pipe.
''')
    wrapper = work / 'server'
    lock = work / 'owned.lock'
    command = [sys.executable, str(parent), str(child), str(lock)]
    wrapper.write_text('#!/bin/sh\nexec ' + shlex.join(command) + '\n')
    wrapper.chmod(0o755)
    server = Server(wrapper, work, work)
    try:
        server.process.wait(timeout=5)
        with lock.open() as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError('the orphaned helper did not retain its lock')
            server.cleanup()
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise AssertionError('fixture cleanup left its helper alive')
                    time.sleep(.01)
    finally:
        server.cleanup()
print('PASS fixture process ownership after parent exit')
