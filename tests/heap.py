#!/usr/bin/env python3
"""Check native Base heap cleanup during real server exchanges on macOS."""
import argparse
from pathlib import Path
import shlex
import sys
import tempfile

import integration


def finish_with_heap_report(self):
    output, errors = integration.finish_process(self.process, timeout=30)
    assert self.process.returncode == 0 and not errors, (self.process.returncode, output, errors)
    assert output.startswith(b'STOPPED\n'), output
    assert b'0 leaks for 0 total leaked bytes' in output, output
    print(output.decode(), end='', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    arguments = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('this check requires the macOS leaks tool')
    with tempfile.TemporaryDirectory(prefix='luce-server-heap-') as temporary:
        root = Path(temporary)
        wrapper = root / 'server-under-leaks'
        wrapper.write_text('#!/bin/sh\nexec /usr/bin/leaks --quiet --noContent --atExit -- '
                           + shlex.quote(str(arguments.binary.resolve())) + ' "$@"\n')
        wrapper.chmod(0o755)
        integration.Server.finish = finish_with_heap_report
        integration.http_tests(wrapper, root)
        integration.tcp_tests(wrapper, root)
        integration.lifetime_tests(wrapper, root)
    print('PASS native heap cleanup: HTTP/WebSocket, TCP, retained bodies and expired views')
