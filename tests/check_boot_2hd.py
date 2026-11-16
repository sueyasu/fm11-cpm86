#!/usr/bin/env python3
"""Check bootable 2HD D88 CHRN, mixed sector sizes and resident layout."""
import pathlib
import struct
import sys
from build_boot_2hd import (CYLINDERS, HEADS, SECTORS, SECTOR_BYTES,
                           RAW_BYTES, SIDE_BYTES, RESERVED_BYTES,
                           RESIDENT_BYTES, HEADER_BYTES, make_d88, build_raw)


def check(ipl_path, bios_path, raw_path, d88_path):
    ipl, bios, raw, d88 = [
        pathlib.Path(path).read_bytes()
        for path in (ipl_path, bios_path, raw_path, d88_path)
    ]
    assert len(ipl) == 512 and len(bios) == 0x1900
    assert len(raw) == RAW_BYTES
    assert d88[0x1b] == 0x20
    assert struct.unpack_from("<I", d88, 0x1c)[0] == len(d88)
    for sector in range(4):
        pos = sector*SECTOR_BYTES
        assert raw[pos:pos+128] == ipl[sector*128:(sector+1)*128]
    # Resident is contiguous from C0/H1/S1; CP/M directory at C2/H0.
    assert raw[SIDE_BYTES+0x2500:SIDE_BYTES+RESIDENT_BYTES] == bios
    assert raw[RESERVED_BYTES:RESERVED_BYTES+32] == b"\xe5"*32

    pos = HEADER_BYTES
    recovered = bytearray(RAW_BYTES)
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
            raw_offset = (track*SECTORS+sector-1)*SECTOR_BYTES
            assert raw[raw_offset:raw_offset+length] == d88[pos:pos+length]
            recovered[raw_offset:raw_offset+length] = d88[pos:pos+length]
            pos += length
    assert pos == len(d88)
    assert recovered[SIDE_BYTES:] == raw[SIDE_BYTES:]

    # Exercise the builder's 4 KiB/EXM=3 allocation-directory path.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp)/"BIG.CMD"
        path.write_bytes(bytes(range(256))*260)  # > 64 KiB, 2 entries
        disk = build_raw(bytes(0x2500),bios,ipl,[path])
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
