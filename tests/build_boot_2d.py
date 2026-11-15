#!/usr/bin/env python3
"""Build a raw FM-11 2D CP/M-86 disk with external .CMD files.

DPB: SPT=32, BSH=4, BLM=15, EXM=1, DSM=151, DRM=63,
AL0=0x80, OFF=4. DSM < 256 means sixteen 8-bit allocation entries
per directory entry; each directory entry covers up to 256 records.
"""
import argparse
import math
from pathlib import Path

CORE_SIZE = 0x2500
BIOS_SIZE = 0x1900
RESIDENT_SIZE = CORE_SIZE + BIOS_SIZE
SECTOR_SIZE = 256
RECORD_SIZE = 128
CYLINDERS = 40
SIDES = 2
SECTORS_PER_SIDE = 16
SIDE_SIZE = SECTOR_SIZE * SECTORS_PER_SIDE
RESERVED_TRACKS = 4
RESERVED_BYTES = SIDE_SIZE * RESERVED_TRACKS
DISK_SIZE = CYLINDERS * SIDES * SIDE_SIZE
BLOCK_SIZE = 2048
TOTAL_BLOCKS = (DISK_SIZE - RESERVED_BYTES) // BLOCK_SIZE
FIRST_FILE_BLOCK = 1                  # AL0 = 0x80, block 0 holds directory
DIRECTORY_ENTRIES = 64
DIRECTORY_BYTES = DIRECTORY_ENTRIES * 32
ALLOCATIONS_PER_ENTRY = 16            # DSM < 256: single-byte block numbers
RECORDS_PER_ENTRY = ALLOCATIONS_PER_ENTRY * (BLOCK_SIZE // RECORD_SIZE)
ERASED = 0xE5
VALID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'()-@^_`{}~"


def cpm_name(path: Path) -> tuple[bytes, bytes]:
    name = path.name.upper()
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    if not (1 <= len(stem) <= 8) or len(ext) > 3:
        raise ValueError(f"{path}: CP/M filename must be 8.3")
    if any(ch not in VALID_CHARS for ch in stem + ext):
        raise ValueError(f"{path}: unsupported CP/M filename characters")
    return stem.ljust(8).encode("ascii"), ext.ljust(3).encode("ascii")


def build_image(core: bytes, bios: bytes, files=()) -> bytes:
    if len(core) != CORE_SIZE:
        raise ValueError(f"CP/M-86 core must be 0x{CORE_SIZE:X} bytes, got {len(core)}")
    if len(bios) != BIOS_SIZE:
        raise ValueError(f"CBIOS must be 0x{BIOS_SIZE:X} bytes, got {len(bios)}")
    if bios[0] != 0xE9:
        raise ValueError("CBIOS must begin with its near JMP BIOS vector")
    if RESIDENT_SIZE > RESERVED_BYTES:
        raise ValueError("resident image does not fit reserved system tracks")

    image = bytearray([ERASED]) * DISK_SIZE
    image[:RESIDENT_SIZE] = core + bios
    directory = bytearray([ERASED]) * DIRECTORY_BYTES
    next_block = FIRST_FILE_BLOCK
    next_entry = 0
    seen = set()

    for path in files:
        path = Path(path)
        name, extension = cpm_name(path)
        key = name + extension
        if key in seen:
            raise ValueError(f"{path}: duplicate CP/M filename")
        seen.add(key)
        data = path.read_bytes()
        total_records = math.ceil(len(data) / RECORD_SIZE)
        remaining = total_records
        source_offset = 0
        extent_base = 0
        # A zero-length file still needs one CP/M directory entry.
        while remaining or extent_base == 0:
            if next_entry >= DIRECTORY_ENTRIES:
                raise ValueError(f"{path}: CP/M directory full")
            records = min(remaining, RECORDS_PER_ENTRY)
            payload_length = min(len(data) - source_offset, records * RECORD_SIZE)
            blocks_needed = math.ceil(payload_length / BLOCK_SIZE)
            if blocks_needed > ALLOCATIONS_PER_ENTRY:
                raise AssertionError("extent needs more than 16 blocks")
            if next_block + blocks_needed > TOTAL_BLOCKS:
                raise ValueError(f"{path}: 2D disk full")

            entry = bytearray(32)
            entry[0] = 0                        # user number
            entry[1:9] = name
            entry[9:12] = extension
            # EXM=1: the low extent bit selects which 128-record
            # subextent of this 256-record directory entry is in use.
            subextent = (records - 1) // 128 if records else 0
            logical_extent = extent_base + subextent
            entry[12] = logical_extent & 0x1F  # EX
            entry[13] = 0                     # S1
            entry[14] = (logical_extent >> 5) & 0x3F  # S2
            entry[15] = records - 128 * subextent   # RC (0..128)
            for index in range(blocks_needed):
                block_number = next_block + index
                entry[16 + index] = block_number    # 8-bit allocation map
                chunk = data[source_offset:source_offset + BLOCK_SIZE]
                dest = RESERVED_BYTES + block_number * BLOCK_SIZE
                image[dest:dest + len(chunk)] = chunk
                source_offset += len(chunk)

            start = next_entry * 32
            directory[start:start + 32] = entry
            next_entry += 1
            next_block += blocks_needed
            remaining -= records
            extent_base += 2                     # EXM+1

    image[RESERVED_BYTES:RESERVED_BYTES + DIRECTORY_BYTES] = directory
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cbios", type=Path, required=True)
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = build_image(args.core.read_bytes(), args.cbios.read_bytes(), args.file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"Created {args.output}: {len(data)} bytes; "
          f"{RESIDENT_SIZE} resident bytes, {RESERVED_TRACKS} reserved side-tracks, "
          f"{len(args.file)} file(s)")


if __name__ == "__main__":
    main()
