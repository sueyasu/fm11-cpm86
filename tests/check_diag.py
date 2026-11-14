#!/usr/bin/env python3
"""Static checks for the optional FM-11 2D read-only diagnostic ROM."""
import pathlib
import sys


def check(path):
    rom = pathlib.Path(path).read_bytes()
    assert len(rom) == 0x1000, f"diagnostic ROM size: {len(rom):#x}"
    assert rom[0xFF0:0xFF5] == bytes((0xEA, 0, 0, 0, 0xFF)), (
        f"incorrect 8088 reset vector: {rom[0xFF0:0xFF5].hex()}"
    )
    for message in (
        b"FM-11 2D DMA read C0/H0/S1",
        b"PASS: TC=1, data: ",
        b"FAIL: FDC status or DMA terminal count",
    ):
        assert message + b"\r\n" in rom or message + b"\0" in rom, (
            f"missing diagnostic message: {message!r}"
        )
    print("PASS: 2D read-only diagnostic ROM layout")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_diag.py fdc2d_diag.bin")
    check(sys.argv[1])
