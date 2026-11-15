#!/usr/bin/env python3
"""Build a 2D bootable D88 from FM-11 CP/M-86 raw image and 512-byte IPL.

Physical geometry: 40 cylinders x 2 heads x 16 sectors x 256 bytes.
The original raw image reserves 0x4000 bytes for CP/M system tracks:
  old 0x0000..0x3DFF: 0x3E00 bytes of CCP/BDOS/CBIOS.
The output keeps the DPB and CP/M directory unchanged:
  new 0x0000..0x01FF: disk IPL loaded by the 8088 boot ROM
  new 0x0200..0x3FFF: the exact same resident image.
  new 0x4000..end:   the exact same CP/M directory and file contents.
"""
import argparse
import struct
from pathlib import Path

CYLINDERS = 40
HEADS = 2
SECTORS = 16
SECTOR_SIZE = 256
TRACKS = CYLINDERS * HEADS
RAW_SIZE = TRACKS * SECTORS * SECTOR_SIZE
RESIDENT_SIZE = 0x3E00
SYSTEM_SIZE = 0x4000
IPL_SIZE = 0x200
D88_HEADER = 0x2B0
SECTOR_HEADER = 16
D88_TRACK_BYTES = SECTORS * (SECTOR_HEADER + SECTOR_SIZE)
D88_SIZE = D88_HEADER + TRACKS * D88_TRACK_BYTES


def insert_ipl(raw: bytes, ipl: bytes) -> bytes:
    if len(raw) != RAW_SIZE:
        raise ValueError(f"raw 2D size must be {RAW_SIZE}, got {len(raw)}")
    if len(ipl) != IPL_SIZE:
        raise ValueError(f"8088 disk IPL must be 0x200 bytes, got {len(ipl):#x}")
    if raw[0x2500] != 0xE9:
        raise ValueError("CBIOS entry vector not found at original raw offset 0x2500")
    if raw[SYSTEM_SIZE - IPL_SIZE:SYSTEM_SIZE] != b"\xe5" * IPL_SIZE:
        raise ValueError("last 512 bytes of reserved area are not free")

    output = bytearray(raw)
    output[0:IPL_SIZE] = ipl
    output[IPL_SIZE:SYSTEM_SIZE] = raw[:RESIDENT_SIZE]
    # directory+files are untouched, and resident still fits OFF=4.
    assert output[SYSTEM_SIZE:] == raw[SYSTEM_SIZE:]
    assert output[IPL_SIZE + 0x2500] == 0xE9
    return bytes(output)


def to_d88(raw: bytes, label: str) -> bytes:
    if len(raw) != RAW_SIZE:
        raise ValueError("invalid 2D raw size")
    try:
        title = label.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("D88 volume name must be ASCII") from exc
    if len(title) > 16:
        raise ValueError("D88 volume name must be at most 16 ASCII characters")

    image = bytearray(D88_SIZE)
    image[:len(title)] = title
    image[0x1A] = 0                   # write-protect disabled
    image[0x1B] = 0                   # 2D media type
    struct.pack_into("<I", image, 0x1C, D88_SIZE)

    pos = D88_HEADER
    for track in range(TRACKS):
        cyl, head = divmod(track, HEADS)
        struct.pack_into("<I", image, 0x20 + track * 4, pos)
        for sector in range(SECTORS):
            header = struct.pack(
                "<BBBBHBBB5sH", cyl, head, sector + 1, 1,
                SECTORS, 0, 0, 0, b"\0" * 5, SECTOR_SIZE
            )
            image[pos:pos + SECTOR_HEADER] = header
            pos += SECTOR_HEADER
            raw_offset = (track * SECTORS + sector) * SECTOR_SIZE
            image[pos:pos + SECTOR_SIZE] = raw[
                raw_offset:raw_offset + SECTOR_SIZE
            ]
            pos += SECTOR_SIZE
    assert pos == len(image)
    return bytes(image)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--ipl", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--raw-output", type=Path)
    p.add_argument("--label", default="FM11 CPM86")
    args = p.parse_args()

    result = insert_ipl(args.raw.read_bytes(), args.ipl.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(to_d88(result, args.label))
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_bytes(result)
    print(f"{args.output}: 2D bootable D88, {D88_SIZE} bytes")
    print("IPL: 0x0000..0x01ff; resident: 0x0200..0x3fff;"
          " CP/M filesystem: 0x4000..end (unchanged)")


if __name__ == "__main__":
    main()
