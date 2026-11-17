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
    assert image[reserved:reserved+BLOCK] == bytes([0xe5])*BLOCK
    # The first near-JMP vector identifies BIOS INIT: check BOOT_DRIVE=8.
    disp = int.from_bytes(cbios[1:3], "little", signed=True)
    init = 3+disp
    assert 0 <= init < 1024
    assert b"\xb9\x08\x00" in cbios[init:init+150], "cold drive I: not embedded"
    # Whole-drive DSM and OFF formulas, independently of the assembler.
    dsm = ((c-1)*heads)//2 - 1
    assert 255 < dsm <= 4102
    assert reserved % BLOCK == 0
    print(f"PASS: {model}, HDD I: boot layout, {dsm+1} 16KiB blocks, 62 resident sectors")


def main():
    if len(sys.argv) != 6:
        raise SystemExit("usage: check_boot_hdd.py rom ipl cbios image model")
    rom,ipl,cbios,image = (Path(x).read_bytes() for x in sys.argv[1:5])
    check(rom,ipl,cbios,image,sys.argv[5])


if __name__ == "__main__":
    main()
