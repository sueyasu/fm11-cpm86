#!/usr/bin/env python3
"""Build a disposable FM-11 2D raw image for the real-CBIOS ROM test.

Physical geometry: 40 cylinders, 2 sides, 16 sectors/side, 256 bytes/sector.
Reserved track zero stores 25 BIOS sectors starting at C0/H0/S2.
Scratch test record is C1/H0/S1 (outside the reserved system tracks).
"""
import argparse
from pathlib import Path

SECTOR_SIZE = 256
CYLINDERS = 40
SIDES = 2
SECTORS = 16
IMAGE_SIZE = CYLINDERS * SIDES * SECTORS * SECTOR_SIZE
BIOS_SIZE = 0x1900


def sector_offset(cylinder, side, sector):
    assert 0 <= cylinder < CYLINDERS
    assert 0 <= side < SIDES
    assert 1 <= sector <= SECTORS
    return ((cylinder * SIDES + side) * SECTORS + sector - 1) * SECTOR_SIZE


def build(bios):
    if len(bios) != BIOS_SIZE:
        raise ValueError(f"CBIOS must be {BIOS_SIZE:#x} bytes, got {len(bios):#x}")

    image = bytearray([0xE5]) * IMAGE_SIZE
    image[:16] = b"FM11 CBIOS TEST\0"
    # Sector 1 is reserved for a future IPL; BIOS starts at sector 2.
    for index in range(BIOS_SIZE // SECTOR_SIZE):
        side, pos = divmod(index + 1, SECTORS)
        offset = sector_offset(0, side, pos + 1)
        image[offset:offset + SECTOR_SIZE] = (
            bios[index * SECTOR_SIZE:(index + 1) * SECTOR_SIZE]
        )

    scratch = sector_offset(1, 0, 1)
    image[scratch:scratch + 128] = bytes(i ^ 0x5A for i in range(128))
    image[scratch + 128:scratch + 256] = bytes(i ^ 0xA5 for i in range(128))
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bios", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    image = build(args.bios.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    print(f"Built {args.output}: {len(image)} bytes (dedicated 2D test disk)")


if __name__ == "__main__":
    main()
