#!/usr/bin/env python3
"""Create a native FM-11 2HD CP/M-86 system disk and bootable D88.

Boot C0/H0: 26 sectors x 128 bytes, FM; IPL in sectors 1..4.
Other tracks: 26 sectors x 256 bytes, MFM.
Resident (0x3E00 bytes): C0/H1/S1 onward, 62 x 256 bytes.
CP/M filesystem: C2/H0 onward (OFF=4), 4 KiB allocation blocks.
The accompanying .raw concatenates actual sector payloads without padding.
"""
from pathlib import Path
import argparse
import math
import struct
from build_boot_2d import cpm_name

CYLINDERS = 77
HEADS = 2
SECTORS = 26
SECTOR_BYTES = 256
SIDE_BYTES = SECTORS * SECTOR_BYTES
BOOT_SECTOR_BYTES = 128
BOOT_SIDE_BYTES = SECTORS * BOOT_SECTOR_BYTES
RAW_BYTES = BOOT_SIDE_BYTES + (CYLINDERS * HEADS - 1) * SIDE_BYTES
RESERVED_SIDES = 4
RESERVED_BYTES = BOOT_SIDE_BYTES + (RESERVED_SIDES - 1) * SIDE_BYTES
RESIDENT_BYTES = 0x3e00
CORE_BYTES = 0x2500
BIOS_BYTES = 0x1900
IPL_BYTES = 512
BLOCK_BYTES = 4096
BLOCKS = (RAW_BYTES - RESERVED_BYTES) // BLOCK_BYTES
DIRECTORY_ENTRIES = 64
RECORD_BYTES = 128
RECORDS_PER_ENTRY = 16 * BLOCK_BYTES // RECORD_BYTES
ERASED = 0xe5
HEADER_BYTES = 0x2b0


def build_raw(core: bytes, bios: bytes, ipl: bytes, files) -> bytes:
    if len(core) != CORE_BYTES or len(bios) != BIOS_BYTES:
        raise ValueError("CP/M core must be 0x2500 and CBIOS exactly 0x1900 bytes")
    if bios[0] != 0xe9:
        raise ValueError("CBIOS first vector is not a near JMP")
    if len(ipl) != IPL_BYTES:
        raise ValueError("2HD IPL must be exactly four 128-byte sectors (512 bytes)")
    if BLOCKS != 243 or RESIDENT_BYTES > (RESERVED_SIDES-1) * SIDE_BYTES:
        raise AssertionError("2HD disk layout and reserved system area disagree")

    raw = bytearray([ERASED]) * RAW_BYTES
    # The first physical side is FM, 26 x 128 bytes in both outputs.
    raw[:IPL_BYTES] = ipl
    raw[BOOT_SIDE_BYTES:BOOT_SIDE_BYTES+RESIDENT_BYTES] = core + bios
    directory = bytearray([ERASED]) * (DIRECTORY_ENTRIES*32)
    used_names = set()
    free_block = 1                # directory takes allocation block zero
    dir_index = 0

    for file in files:
        file = Path(file)
        name, extension = cpm_name(file)
        key = name + extension
        if key in used_names:
            raise ValueError(f"duplicate CP/M file: {file}")
        used_names.add(key)
        payload = file.read_bytes()
        remaining = math.ceil(len(payload)/RECORD_BYTES)
        src = 0
        extent = 0
        while remaining or extent == 0:
            if dir_index >= DIRECTORY_ENTRIES:
                raise ValueError("CP/M directory full")
            records = min(remaining, RECORDS_PER_ENTRY)
            length = min(len(payload)-src, records*RECORD_BYTES)
            need = math.ceil(length/BLOCK_BYTES)
            if free_block + need > BLOCKS:
                raise ValueError(f"2HD filesystem is full: {file}")
            entry = bytearray(32)
            entry[0] = 0
            entry[1:9] = name
            entry[9:12] = extension
            subextent = (records-1)//128 if records else 0
            logical_extent = extent + subextent
            entry[12] = logical_extent & 31
            entry[14] = (logical_extent >> 5) & 63
            entry[15] = records - subextent*128
            for i in range(need):
                block = free_block+i
                entry[16+i] = block          # DSM=242 -> 8-bit block numbers
                data = payload[src:src+BLOCK_BYTES]
                dest = RESERVED_BYTES + block*BLOCK_BYTES
                raw[dest:dest+len(data)] = data
                src += len(data)
            directory[dir_index*32:(dir_index+1)*32] = entry
            dir_index += 1
            free_block += need
            remaining -= records
            extent += 4                     # EXM=3: four 128-record extents
    raw[RESERVED_BYTES:RESERVED_BYTES+len(directory)] = directory
    return bytes(raw)


def make_d88(raw: bytes, label: str) -> bytes:
    if len(raw) != RAW_BYTES:
        raise ValueError("wrong 2HD raw disk size")
    title = label.encode("ascii")
    if len(title) > 16:
        raise ValueError("D88 title must not exceed 16 ASCII bytes")
    out = bytearray(HEADER_BYTES)
    out[:len(title)] = title
    out[0x1b] = 0x20
    offset = 0
    for side_track in range(CYLINDERS*HEADS):
        struct.pack_into("<I", out, 0x20+4*side_track, len(out))
        cyl, head = divmod(side_track, 2)
        length = 128 if side_track == 0 else 256
        n = 0 if length == 128 else 1
        density = 0x40 if side_track == 0 else 0x00
        for index in range(SECTORS):
            sector = index+1
            out += struct.pack("<BBBBHBBB5sH", cyl, head, sector, n,
                               SECTORS, density, 0, 0, b"\0"*5, length)
            out += raw[offset:offset+length]
            offset += length
    assert offset == len(raw)
    struct.pack_into("<I", out, 0x1c, len(out))
    return bytes(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--core", required=True, type=Path)
    p.add_argument("--cbios", required=True, type=Path)
    p.add_argument("--ipl", required=True, type=Path)
    p.add_argument("--file", action="append", default=[], type=Path)
    p.add_argument("--raw-output", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--label", default="FM11 CPM86 2HD")
    args = p.parse_args()
    raw = build_raw(args.core.read_bytes(), args.cbios.read_bytes(),
                    args.ipl.read_bytes(), args.file)
    d88 = make_d88(raw, args.label)
    for path, contents in ((args.raw_output, raw), (args.output, d88)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    print(f"{args.output}: 2HD D88 {len(d88)} bytes; raw={len(raw)} bytes")
    print("2HD boot drive is E:, C0/H0 is FM 128-byte IPL; C0/H1.. system")


if __name__ == "__main__":
    main()
