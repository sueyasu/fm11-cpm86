#!/usr/bin/env python3
"""Check FM-11 2D D88 geometry, IPL placement and CP/M image identity."""
import importlib.util
import pathlib
import struct
import sys

def main():
    if len(sys.argv) != 5:
        raise SystemExit("usage: check_boot_d88.py raw.img ipl.bin boot.d88 boot.raw")
    raw, ipl, d88, boot = [pathlib.Path(x).read_bytes() for x in sys.argv[1:]]
    assert len(raw) == len(boot) == 40 * 2 * 16 * 256
    assert len(ipl) == 512
    assert boot[:512] == ipl
    assert boot[512:0x4000] == raw[:0x3E00]
    assert boot[0x4000:] == raw[0x4000:]
    assert boot[512 + 0x2500] == 0xE9
    assert len(d88) == 0x2B0 + 80 * 16 * 272
    assert d88[0x1b] == 0
    assert struct.unpack_from("<I", d88, 0x1c)[0] == len(d88)
    pos = 0x2b0
    recovered = bytearray()
    for i in range(80):
        assert struct.unpack_from("<I", d88, 0x20 + 4 * i)[0] == pos
        for sector in range(16):
            h = d88[pos:pos+16]
            assert (h[0], h[1], h[2], h[3]) == (i//2, i%2, sector+1, 1)
            assert struct.unpack_from("<H", h, 4)[0] == 16
            assert struct.unpack_from("<H", h, 14)[0] == 256
            pos += 16
            recovered.extend(d88[pos:pos+256])
            pos += 256
    assert pos == len(d88)
    assert bytes(recovered) == boot
    print("PASS: 8088 IPL + shifted resident + unchanged CP/M filesystem + D88 CHRN")

if __name__ == "__main__":
    main()
