#!/usr/bin/env python3
"""Build a whole-physical-FM11-MDC-HDD CP/M-86 boot image, no partitions.

HDD IPL at LBA0-1, resident at LBA2-63, cylinder 0 reserved.
CP/M-86 I: uses 64 128-byte logical records per head-track,
OFF=heads, 16-KiB allocation blocks, 512 directory entries and
16-bit block numbers. Files are imported as CP/M 8.3 extents.
"""
import argparse
import math
from pathlib import Path
from build_boot_2d import cpm_name

MODELS = {
    "m2230b": (315, 2), "m2231b": (157, 4), "m2232b": (157, 6),
    "m2233b": (315, 4), "m2234b": (315, 6), "m2235b": (315, 8),
    "m2241b": (747, 4), "m2242b": (747, 7), "m2243b": (747, 11),
}
SECTOR = 256
SPT = 32
BLOCK = 16384
DIRECTORY_ENTRIES = 512
DIRECTORY_BYTES = DIRECTORY_ENTRIES * 32
RECORD = 128
RESIDENT_SIZE = 0x3E00
ALLOCATIONS_PER_ENTRY = 8    # DSM > 255: eight 16-bit pointers
RECORDS_PER_ENTRY = ALLOCATIONS_PER_ENTRY * BLOCK // RECORD
ERASED = 0xE5


def build_image(model: str, ipl: bytes, core: bytes, cbios: bytes, files=()) -> bytes:
    cylinders, heads = MODELS[model]
    size = cylinders * heads * SPT * SECTOR
    reserved = heads * SPT * SECTOR
    if len(ipl) != 512 or len(core) != 0x2500 or len(cbios) != 0x1900:
        raise ValueError("IPL must be 512, core 0x2500, CBIOS 0x1900 bytes")
    if ipl[0] != 0xFA or cbios[0] != 0xE9:
        raise ValueError("invalid HDD IPL or CBIOS signature")
    if reserved < 512 + RESIDENT_SIZE:
        raise ValueError("HDD reserved cylinder too small")
    total_blocks = (size-reserved)//BLOCK
    if not 256 < total_blocks < 65536:
        raise ValueError("DSM must use two-byte allocation pointers")
    # Disk initialized in E5, which is a valid empty CP/M directory.
    image = bytearray([ERASED]) * size
    image[:512] = ipl
    image[512:512+RESIDENT_SIZE] = core + cbios
    seen = set()
    block_index = 1
    entry_index = 0
    for path in files:
        path = Path(path)
        stem, ext = cpm_name(path)
        name = stem+ext
        if name in seen:
            raise ValueError(f"{path}: duplicate CP/M filename")
        seen.add(name)
        data = path.read_bytes()
        records_total = math.ceil(len(data)/RECORD)
        records_left = records_total
        cursor = 0
        extent_base = 0
        while records_left or extent_base == 0:
            if entry_index >= DIRECTORY_ENTRIES:
                raise ValueError(f"{path}: HDD directory full")
            records = min(records_left, RECORDS_PER_ENTRY)
            used_bytes = min(len(data)-cursor, records*RECORD)
            used_blocks = math.ceil(used_bytes/BLOCK)
            if block_index + used_blocks > total_blocks:
                raise ValueError(f"{path}: HDD full")
            entry = bytearray(32)
            entry[0] = 0
            entry[1:9] = stem
            entry[9:12] = ext
            subextent = (records-1)//128 if records else 0
            logical_extent = extent_base+subextent
            entry[12] = logical_extent & 31
            entry[13] = 0
            entry[14] = (logical_extent>>5)&63
            entry[15] = records - 128*subextent
            for j in range(used_blocks):
                dest = reserved + (block_index+j)*BLOCK
                chunk = data[cursor:cursor+BLOCK]
                image[dest:dest+len(chunk)] = chunk
                entry[16+j*2:18+j*2] = (block_index+j).to_bytes(2, "little")
                cursor += len(chunk)
            d = reserved + entry_index*32
            image[d:d+32] = entry
            block_index += used_blocks
            records_left -= records
            extent_base += 8
            entry_index += 1
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, default="m2233b")
    parser.add_argument("--ipl", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cbios", type=Path, required=True)
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = build_image(args.model, args.ipl.read_bytes(), args.core.read_bytes(),
                       args.cbios.read_bytes(), args.file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}: {len(data)} bytes; model={args.model}, "
          f"{len(args.file)} CP/M file(s), boot drive I:")


if __name__ == "__main__":
    main()
