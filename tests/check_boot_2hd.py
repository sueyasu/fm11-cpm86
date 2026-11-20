#!/usr/bin/env python3
"""Check bootable 2HD D88 CHRN, mixed sector sizes and resident layout."""
import pathlib
import struct
import sys
from build_boot_2hd import (CYLINDERS, HEADS, SECTORS, BOOT_SIDE_BYTES,
                           RAW_BYTES, RESERVED_BYTES,
                           RESIDENT_BYTES, HEADER_BYTES, make_d88, build_raw)


def check_directory(raw):
    directory = raw[RESERVED_BYTES:RESERVED_BYTES + 64*32]
    assert len(directory) == 64*32
    for i in range(0, len(directory), 32):
        entry = directory[i:i+32]
        if entry[0] == 0xe5:
            continue
        assert 0 <= entry[0] <= 15, f"invalid CP/M user in directory entry {i//32}"
        assert entry[1:9].strip(b" "), f"empty filename in directory entry {i//32}"
        # DSM=242, with single-byte block numbers.
        assert all(block <= 242 for block in entry[16:32]), (
            f"allocation number out of range in entry {i//32}"
        )


def check(ipl_path, bios_path, raw_path, d88_path):
    ipl, bios, raw, d88 = [
        pathlib.Path(path).read_bytes()
        for path in (ipl_path, bios_path, raw_path, d88_path)
    ]
    assert len(ipl) == 512 and len(bios) == 0x1900
    assert len(raw) == RAW_BYTES == 1021696
    assert BOOT_SIDE_BYTES == 0x0d00
    assert RESERVED_BYTES == 0x5b00
    assert d88[0x1b] == 0x20
    assert struct.unpack_from("<I", d88, 0x1c)[0] == len(d88)
    assert raw[:512] == ipl
    # Resident is contiguous from C0/H1/S1; CP/M directory at C2/H0.
    assert raw[BOOT_SIDE_BYTES+0x2500:BOOT_SIDE_BYTES+RESIDENT_BYTES] == bios
    # A boot image may contain imported .CMD files.  Empty directory
    # slots are E5h; occupied entries have a valid CP/M user number.
    # Do not require the first entry to be empty.
    check_directory(raw)

    pos = HEADER_BYTES
    recovered = bytearray()
    for track in range(CYLINDERS*HEADS):
        assert struct.unpack_from("<I", d88, 0x20+4*track)[0] == pos
        cyl, head = divmod(track, 2)
        length = 128 if track == 0 else 256
        n = 0 if track == 0 else 1
        density = 0x40 if track == 0 else 0
        for sector in range(1,SECTORS+1):
            ch, hh, sid, sn, count, den, _, _, _, size = \
                struct.unpack_from("<BBBBHBBB5sH", d88, pos)
            assert (ch,hh,sid,sn,count,den,size) == (
                cyl,head,sector,n,SECTORS,density,length)
            pos += 16
            recovered.extend(d88[pos:pos+length])
            pos += length
    assert pos == len(d88)
    assert recovered == raw, "RAW must equal concatenated D88 sector payloads"

    # Exercise the builder's 4 KiB/EXM=3 allocation-directory path.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp)/"BIG.CMD"
        path.write_bytes(bytes(range(256))*260)  # > 64 KiB, 2 entries
        disk = build_raw(bytes(0x2500),bios,ipl,[path])
        # Regression: populated images must pass the same directory
        # validation used for bootable images with imported .CMD files.
        check_directory(disk)
        corrupted = bytearray(disk)
        corrupted[RESERVED_BYTES] = 0x30
        try:
            check_directory(corrupted)
            raise AssertionError("invalid CP/M directory user was accepted")
        except AssertionError as exc:
            if "invalid CP/M user" not in str(exc):
                raise
        directory = disk[RESERVED_BYTES:RESERVED_BYTES+64]
        assert directory[:1] == b"\x00"
        assert directory[32:33] == b"\x00"
        assert directory[1:9] == b"BIG     "
        assert directory[12] == 3 and directory[15] == 128
        assert directory[32+12] == 4
        assert directory[16:32] == bytes(range(1,17))
        assert disk[RESERVED_BYTES+4096:RESERVED_BYTES+4096+256] == bytes(range(256))
        assert make_d88(disk,"TEST")[0x1b] == 0x20
    print("PASS: 2HD FM IPL, DMA resident layout, D88 128/256 CHRN and directory extents")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: check_boot_2hd.py ipl.bin cbios_2hd.bin boot.raw boot.d88")
    check(*sys.argv[1:])
