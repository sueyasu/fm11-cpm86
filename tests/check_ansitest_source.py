#!/usr/bin/env python3
"""Check that ANSITEST.A86 is a CP/M ASM86-compatible text file."""
from pathlib import Path
import re

data = Path("command/ANSITEST.A86").read_bytes()
assert data.endswith(b"\x1a"), "CP/M text must end with Ctrl-Z"
body = data[:-1]
assert body.count(b"\r\n") > 0
assert body.count(b"\n") == body.count(b"\r\n"), "bare LF found"
assert body.count(b"\r") == body.count(b"\r\n"), "bare CR found"
assert all(len(line) <= 127 for line in body.split(b"\r\n")), "line too long"
source = body.decode("ascii")
assert "cseg\r\n" in source and "dseg\r\norg     100h" in source
assert re.search(r"^end\r?$", source, re.M | re.I)
print("PASS: CP/M ASM86 ANSI test source has CRLF lines and Ctrl-Z EOF")
