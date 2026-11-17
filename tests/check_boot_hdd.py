#!/usr/bin/env python3
"""Verify the native FM-11 HDD ROM/ipl/CBIOS layout without CP/M core."""
import sys
from pathlib import Path
from build_boot_hdd import MODELS, BLOCK, SECTOR, SPT, RESIDENT_SIZE


def check(rom, ipl, cbios, image, model):
    c, heads = MODELS[model]
    assert len(rom) == 4096 and rom[0xff0:0xff5] == bytes.fromhex("ea 00 00 00 ff")
    assert len(ipl) == 512 and ipl[0] == 0xfa
    assert len(cbios) == 0x1900 and cbios[0] == 0xe9
    assert len(image) == c*heads*SPT*SECTOR
    assert image[:512] == ipl
    assert image[512+0x2500:512+RESIDENT_SIZE] == cbios
    assert image[512+RESIDENT_SIZE:heads*SPT*SECTOR] == bytes([0xe5]) * (
        heads*SPT*SECTOR-512-RESIDENT_SIZE)
    reserved = heads*SPT*SECTOR
    # The directory is empty for a synthetic CI image, but a normal
    # boot-hdd build imports external/commands files into this block.
    # Validate occupied CP/M directory entries and erased unused slots.
    directory = image[reserved:reserved+BLOCK]
    assert len(directory) == BLOCK
    used_entries = 0
    free_seen = False
    allocated_blocks = set()
    total_blocks = (len(image)-reserved)//BLOCK
    for offset in range(0, BLOCK, 32):
        entry = directory[offset:offset+32]
        if entry[0] == 0xe5:
            assert entry == bytes([0xe5])*32, (
                f"directory entry {offset//32}: partially erased")
            free_seen = True
            continue
        assert not free_seen, "directory entries after first unused slot"
        assert entry[0] == 0, f"unsupported user number at {offset//32}"
        assert any(ch != 0x20 for ch in entry[1:9]), "empty CP/M filename"
        assert all(0x20 <= ch < 0x7f for ch in entry[1:12]), (
            f"invalid CP/M name in entry {offset//32}")
        for slot in range(8):
            block = int.from_bytes(entry[16+2*slot:18+2*slot], "little")
            if block:
                assert 1 <= block < total_blocks, f"block {block} out of range"
                assert block not in allocated_blocks, f"duplicate block {block}"
                allocated_blocks.add(block)
        used_entries += 1
    # The first near-JMP vector identifies BIOS INIT: check BOOT_DRIVE=8.
    disp = int.from_bytes(cbios[1:3], "little", signed=True)
    init = 3+disp
    assert 0 <= init < 1024
    assert b"\xb9\x08\x00" in cbios[init:init+150], "cold drive I: not embedded"
    # Whole-drive DSM and OFF formulas, independently of the assembler.
    dsm = ((c-1)*heads)//2 - 1
    assert 255 < dsm <= 4102
    assert reserved % BLOCK == 0
    print(f"PASS: {model}, HDD I: boot layout, {dsm+1} 16KiB blocks, "
          f"62 resident sectors, {used_entries} directory entries")


def main():
    if len(sys.argv) != 6:
        raise SystemExit("usage: check_boot_hdd.py rom ipl cbios image model")
    rom,ipl,cbios,image = (Path(x).read_bytes() for x in sys.argv[1:5])
    check(rom,ipl,cbios,image,sys.argv[5])


if __name__ == "__main__":
    main()
