#!/usr/bin/env python3
"""Check ASM86 IPL INCLUDE round-trip, text syntax and exact 512-byte payload."""
import pathlib
import re
import sys

PATTERN = re.compile(r"0([0-9A-F]{2})h")


def check(src, include, name):
    binary = pathlib.Path(src).read_bytes()
    data = pathlib.Path(include).read_bytes()
    assert data.endswith(b"\x1a"), "ASM86 text EOF (1Ah) is required"
    text = data[:-1].decode("ascii")
    assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
    assert f"{name}:\r\n" in text
    lines = [line.strip() for line in text.splitlines()
             if line.strip().startswith("DB")]
    assert lines
    recovered = bytearray()
    for line in lines:
        assert line.startswith("DB      ")
        items = line[8:].split(",")
        assert 1 <= len(items) <= 16
        for item in items:
            assert PATTERN.fullmatch(item), repr(item)
            recovered.append(int(item[1:-1], 16))
    assert len(binary) == 512
    assert bytes(recovered) == binary, f"{src}: INC payload mismatch"


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: check_fdformat_inc.py ipl2d.bin ipl2hd.bin FDIPL2D.INC FDIPL2HD.INC")
    check(sys.argv[1],sys.argv[3],"fdipl2d_template")
    check(sys.argv[2],sys.argv[4],"fdipl2hd_template")
    print("PASS: two 512-byte ASM86 IPL includes round-trip and carry 1Ah EOF")
