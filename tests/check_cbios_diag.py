#!/usr/bin/env python3
"""Validate the ROM and disposable 2D disk layout for the CBIOS test."""
import pathlib
import sys


def check(rom_path, disk_path, bios_path):
    rom = pathlib.Path(rom_path).read_bytes()
    disk = pathlib.Path(disk_path).read_bytes()
    bios = pathlib.Path(bios_path).read_bytes()

    assert len(rom) == 0x1000, f"CBIOS diagnostic ROM: {len(rom):#x}"
    assert rom[0xFF0:0xFF5] == bytes((0xEA, 0, 0, 0, 0xFF)), (
        "invalid reset vector"
    )
    for phrase in (b"CBIOS 128-byte record test", b"CBIOS DMA transfers completed (checking image)",
                   b"PASS: records 0 and 1 read",
                   b"PASS: WRITE, RMW, verify, restore"):
        assert phrase in rom, f"missing diagnostic text: {phrase!r}"

    assert len(bios) == 0x1900, f"CBIOS size: {len(bios):#x}"
    assert len(disk) == 40 * 2 * 16 * 256, f"2D disk size: {len(disk):#x}"
    for i in range(25):
        side, sector_index = divmod(i + 1, 16)
        start = ((side * 16) + sector_index) * 256
        assert disk[start:start + 256] == bios[i * 256:(i + 1) * 256], (
            f"BIOS sector mismatch: index {i}"
        )
    scratch = (2 * 16) * 256  # C=1, H=0, S=1
    assert disk[scratch:scratch + 128] == bytes(i ^ 0x5A for i in range(128))
    assert disk[scratch + 128:scratch + 256] == bytes(
        i ^ 0xA5 for i in range(128)
    )
    print("PASS: CBIOS diagnostic ROM and 2D scratch image layout")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: check_cbios_diag.py ROM.bin DISK.img CBIOS.bin")
    check(*sys.argv[1:])
