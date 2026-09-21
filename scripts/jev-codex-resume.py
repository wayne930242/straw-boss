#!/usr/bin/env python3
"""Receive a memory-only launch environment and replace this process with Codex."""
import argparse
import json
import os
import socket

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--socket', required=True)
args = parser.parse_args()
with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(30)
    client.connect(args.socket)
    data = bytearray()
    while chunk := client.recv(65536):
        data.extend(chunk)
request = json.loads(data)
os.chdir(request['cwd'])
os.execve(request['argv'][0], request['argv'], request['env'])
