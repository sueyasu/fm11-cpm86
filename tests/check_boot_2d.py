#!/usr/bin/env python3
"""Static boot image tests using a synthetic open test core, no CP/M binary."""
import pathlib
import sys

from build_boot_2d import (
    BIOS_SIZE, CORE_SIZE, DISK_SIZE, RESERVED_BYTES, RESIDENT_SIZE,
    DIRECTORY_BYTES, build_image,
)


def check(rom, bios_path):
    bootrom = pathlib.Path(rom).read_bytes()
    bios = pathlib.Path(bios_path).read_bytes()
    assert len(bootrom) == 0x1000
    assert bootrom[0xFF0:0xFF5] == bytes((0xEA, 0, 0, 0, 0xFF))
    for text in (b"FM-11 CP/M-86 2D IPL: loading resident",
                 b"FM-11 CP/M-86 IPL: CBIOS vector OK, entering INIT",
                 b"FAIL: resident sector read / DMA"):
        assert text in bootrom
    assert len(bios) == BIOS_SIZE
    core = bytes(i & 0xFF for i in range(CORE_SIZE))
    image = build_image(core, bios)
    assert len(image) == DISK_SIZE
    assert image[:CORE_SIZE] == core
    assert image[CORE_SIZE:RESIDENT_SIZE] == bios
    assert image[RESIDENT_SIZE:RESERVED_BYTES] == (
        bytes([0xE5]) * (RESERVED_BYTES - RESIDENT_SIZE)
    )
    assert image[RESERVED_BYTES:RESERVED_BYTES + DIRECTORY_BYTES] == (
        bytes([0xE5]) * DIRECTORY_BYTES
    )
    try:
        build_image(core[:-1], bios)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong core size must be rejected")
    print("PASS: IPL ROM layout and synthetic CP/M-86 boot image")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_boot_2d.py IPLROM.bin CBIOS.bin")
    check(*sys.argv[1:])
