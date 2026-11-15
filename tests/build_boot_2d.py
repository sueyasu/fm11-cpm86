#!/usr/bin/env python3
"""Generate a raw 320 KiB bootable-intent FM-11 CP/M-86 2D image.

The boot ROM loads 62 consecutive 256-byte physical sectors from C0/H0/S1
into resident segment 0800h: core 0x2500 bytes followed by CBIOS 0x1900.
Four side-tracks (two cylinders, 16384 bytes) are reserved, with the CP/M
directory starting at cylinder 2 side 0. No proprietary core is bundled.
"""
import argparse
from pathlib import Path

CORE_SIZE = 0x2500
BIOS_SIZE = 0x1900
RESIDENT_SIZE = CORE_SIZE + BIOS_SIZE
SECTOR_SIZE = 256
CYLINDERS = 40
SIDES = 2
SECTORS_PER_SIDE = 16
SIDE_SIZE = SECTOR_SIZE * SECTORS_PER_SIDE
RESERVED_TRACKS = 4
RESERVED_BYTES = SIDE_SIZE * RESERVED_TRACKS
DISK_SIZE = CYLINDERS * SIDES * SIDE_SIZE
DIRECTORY_ENTRIES = 64
DIRECTORY_BYTES = DIRECTORY_ENTRIES * 32


def build_image(core: bytes, bios: bytes) -> bytes:
    if len(core) != CORE_SIZE:
        raise ValueError(f"CP/M-86 core must be 0x{CORE_SIZE:X} bytes, got {len(core)}")
    if len(bios) != BIOS_SIZE:
        raise ValueError(f"CBIOS must be 0x{BIOS_SIZE:X} bytes, got {len(bios)}")
    if bios[0] != 0xE9:
        raise ValueError("CBIOS must begin with its near JMP BIOS vector")
    resident = core + bios
    if len(resident) > RESERVED_BYTES:
        raise ValueError("resident image does not fit reserved system tracks")
    image = bytearray([0xE5]) * DISK_SIZE
    image[:RESIDENT_SIZE] = resident
    # CP/M-86 AL0=80h: the first 2 KiB block is reserved for the
    # directory. Its bytes remain E5h for an empty directory.
    if image[RESERVED_BYTES:RESERVED_BYTES + DIRECTORY_BYTES] != (
        bytes([0xE5]) * DIRECTORY_BYTES
    ):
        raise AssertionError("directory should begin empty")
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cbios", type=Path, required=True)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = build_image(args.core.read_bytes(), args.cbios.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"Created {args.output}: {len(data)} bytes; "
          f"{RESIDENT_SIZE} resident bytes, {RESERVED_TRACKS} reserved side-tracks")


if __name__ == "__main__":
    main()
