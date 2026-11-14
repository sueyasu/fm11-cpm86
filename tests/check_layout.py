#!/usr/bin/env python3
"""Static checks of the initial FM-11 8088 firmware/CP/M-86 BIOS ABI."""
import pathlib
import sys

def check(bios_path, rom_path):
    bios = pathlib.Path(bios_path).read_bytes()
    rom = pathlib.Path(rom_path).read_bytes()
    assert len(bios) == 0x1900, f"CBIOS size: {len(bios):#x}"
    assert len(rom) == 0x1000, f"ROM size: {len(rom):#x}"
    # 21 near JMP vectors, each exactly three bytes (E9 relative16).
    for index in range(21):
        assert bios[index * 3] == 0xE9, f"BIOS vector {index} is not JMP near"
        displacement = int.from_bytes(bios[index*3+1:index*3+3], "little", signed=True)
        target = 0x2500 + (index+1)*3 + displacement
        assert 0x2500 <= target < 0x3E00, f"invalid BIOS vector target {index}: {target:#x}"
    # 8088 reset vector at FFFF0 must jump far to FF00:0000.
    assert rom[0xFF0:0xFF5] == bytes([0xEA, 0x00, 0x00, 0x00, 0xFF]), (
        f"bad reset vector: {rom[0xFF0:0xFF5].hex()}")
    print("PASS: FM-11 CP/M-86 BIOS vector table and 8088 reset ROM")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_layout.py CBIOS.bin bootrom.bin")
    check(sys.argv[1], sys.argv[2])
