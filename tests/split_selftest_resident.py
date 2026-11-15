#!/usr/bin/env python3
"""Split a linked self-test resident image into the fixed IPL disk layout."""
import pathlib
import sys

CORE_SIZE = 0x2500
BIOS_SIZE = 0x1900

def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: split_selftest_resident.py combined.bin core.bin cbios.bin")
    image = pathlib.Path(sys.argv[1]).read_bytes()
    assert len(image) == CORE_SIZE + BIOS_SIZE, (
        f"self-test resident must be 0x3E00 bytes, got {len(image):#x}"
    )
    core = image[:CORE_SIZE]
    bios = image[CORE_SIZE:]
    assert bios[0] == 0xE9, "CBIOS vector table not at offset 0x2500"
    pathlib.Path(sys.argv[2]).write_bytes(core)
    pathlib.Path(sys.argv[3]).write_bytes(bios)
    print("PASS: self-test core 0x2500 + CBIOS 0x1900")
if __name__ == "__main__":
    main()
