#!/usr/bin/env python3
"""Check the exact CBIOS INIT byte sequence that FORMAT /S patches.

The formatter recognizes an existing on-disk CBIOS by following the
first near JMP vector to INIT, then scanning 96 bytes for the pair of
cur_disk / BDOS CURDRV stores after MOV CX,BOOT_DRIVE. Verify all three
boot-family builds, the rewritten cold-drive byte, and rejection of
unknown binaries without touching them.
"""
from pathlib import Path
import sys

SIGNATURE_PREFIX = bytes.fromhex("88 0e")
SIGNATURE_END = bytes.fromhex("88 0e b7 24")


def find_patch_offset(bios: bytes) -> int:
    if len(bios) != 0x1900 or bios[0] != 0xe9:
        raise ValueError("invalid CBIOS image")
    displacement = int.from_bytes(bios[1:3], "little", signed=True)
    init = 3 + displacement
    if not (0 <= init <= len(bios)-96-11):
        raise ValueError("bad CBIOS INIT vector")
    matches = []
    for i in range(init, init+96):
        if (bios[i] == 0xb9 and bios[i+1] in (0, 4, 8)
                and bios[i+2] == 0
                and bios[i+3:i+5] == SIGNATURE_PREFIX
                and bios[i+7:i+11] == SIGNATURE_END):
            matches.append(i+1)
    if len(matches) != 1:
        raise ValueError(f"expected one INIT drive site, found {len(matches)}")
    return matches[0]


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: check_fdformat_boot_patch.py cbios.bin cbios_2hd.bin cbios_hdd.bin")
    originals = [Path(path).read_bytes() for path in sys.argv[1:]]
    offsets = [find_patch_offset(bios) for bios in originals]
    assert len(set(offsets)) == 1, f"INIT patch offsets disagree: {offsets}"
    position = offsets[0]
    assert [bios[position] for bios in originals] == [0, 4, 8]
    for original in originals:
        for target in (0, 4, 8):
            output = bytearray(original)
            output[position] = target
            assert find_patch_offset(output) == position
            assert output[position] == target
            assert bytes(output[:position] + output[position+1:]) == (
                original[:position] + original[position+1:])
    corrupt = bytearray(originals[2])
    corrupt[position+9] = 0
    try:
        find_patch_offset(corrupt)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid CBIOS unexpectedly patchable")
    print(f"PASS: A:/E:/I: CBIOS INIT boot-drive patch at BIOS +{position:#x}")


if __name__ == "__main__":
    main()
