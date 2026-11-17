#!/usr/bin/env python3
"""Check the exact CBIOS INIT byte sequence that FDFORMAT /S patches.

The formatter recognizes an existing on-disk CBIOS by following the
first near JMP vector to INIT, then scanning 96 bytes for the pair of
cur_disk / BDOS CURDRV stores after MOV CX,BOOT_DRIVE. Verify both
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
        if (bios[i] == 0xb9 and bios[i+1] in (0, 4)
                and bios[i+2] == 0
                and bios[i+3:i+5] == SIGNATURE_PREFIX
                and bios[i+7:i+11] == SIGNATURE_END):
            matches.append(i+1)
    if len(matches) != 1:
        raise ValueError(f"expected one INIT drive site, found {len(matches)}")
    return matches[0]


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_fdformat_boot_patch.py cbios.bin cbios_2hd.bin")
    original_2d = Path(sys.argv[1]).read_bytes()
    original_2hd = Path(sys.argv[2]).read_bytes()
    first = find_patch_offset(original_2d)
    second = find_patch_offset(original_2hd)
    assert first == second
    assert original_2d[first] == 0 and original_2hd[second] == 4
    for original, expected in ((original_2d, 4), (original_2hd, 0)):
        output = bytearray(original)
        output[find_patch_offset(output)] = expected
        assert find_patch_offset(output) == first
        assert output[first] == expected
        assert bytes(output[:first] + output[first+1:]) == (
            original[:first] + original[first+1:])
    corrupt = bytearray(original_2hd)
    corrupt[first+9] = 0
    try:
        find_patch_offset(corrupt)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid CBIOS unexpectedly patchable")
    print(f"PASS: 2D/2HD CBIOS INIT cold boot drive patch at BIOS +{first:#x}")


if __name__ == "__main__":
    main()
