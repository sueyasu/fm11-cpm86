#!/usr/bin/env python3
"""Static/model checks for 8 KiB RAM sizing with destructive readback.

Test mirrored RAM and unmapped (non-mirrored) high addresses, including
correct byte restoration, all 113 supported 8 KiB capacities, and the
final 4 KiB ROM boundary. This does not execute the 8086 instructions.
"""
from pathlib import Path
import sys

source = Path("src/cbios.asm").read_text()
init = source.split("\nINIT:\n", 1)[1].split("\nWBOOT:\n", 1)[0]
assert "call init_mrt" in init
assert init.index("call init_mrt") < init.index("jmp 0x0000")
section = source.split("\ninit_mrt:\n", 1)[1].split("\nGETIOBF:\n", 1)[0]
for instruction in (
    "RAM_PROBE_OFF equ 0x0500",
    "push ds",
    "push es",
    "xor ax,ax",
    "mov ds,ax",
    "mov al,[RAM_PROBE_OFF]",
    "mov byte [RAM_PROBE_OFF],0x5a",
    "mov bx,0x1000",
    "mov cx,120",
    "mov dl,[es:RAM_PROBE_OFF]",
    "mov byte [es:RAM_PROBE_OFF],0x55",
    "cmp byte [es:RAM_PROBE_OFF],0x55",
    "cmp byte [RAM_PROBE_OFF],0x5a",
    "mov byte [es:RAM_PROBE_OFF],0xaa",
    "cmp byte [es:RAM_PROBE_OFF],0xaa",
    "jne .absent",
    "mov [es:RAM_PROBE_OFF],dl",
    "add bx,0x0200",
    "loop .probe",
    "mov word [cs:mrt_tpa_len],0xf700",
    ".absent:",
    "sub bx,0x0800",
    "mov [cs:mrt_tpa_len],bx",
    "mov [RAM_PROBE_OFF],al",
    "pop es",
    "pop ds",
):
    if instruction not in source and instruction != "RAM_PROBE_OFF equ 0x0500":
        assert instruction in section, f"missing RAM probe instruction: {instruction}"
    else:
        assert instruction in source, f"missing RAM probe definition: {instruction}"
assert "ram_probe_anchor:" not in source
assert "dw 0x0800\nmrt_tpa_len:\n    dw 0x7800" in source

ANCHOR_PHYS = 0x0500
ROM_START = 0xFF000
FIRST_KIB = 64
PROBE_COUNT = 120
assert ANCHOR_PHYS + FIRST_KIB * 1024 == 0x10500
assert ANCHOR_PHYS + (FIRST_KIB + (PROBE_COUNT - 1) * 8) * 1024 == 0xFE500
assert 0xFE500 < ROM_START


def simulate(kib, unpopulated="mirror"):
    capacity = kib * 1024
    ram = bytearray(capacity)
    # Give every probed offset a distinct starting value, so corrupting
    # any read/write candidate is detected even if it is not the anchor.
    for physical in range(ANCHOR_PHYS, ROM_START, 0x2000):
        if unpopulated == "mirror" or physical < capacity:
            ram[physical % capacity] = (physical >> 13) & 0xFF
    before = ram[:]

    def read(physical):
        if physical >= capacity and unpopulated != "mirror":
            return 0xFF if unpopulated == "ff" else 0x00
        return ram[physical % capacity]

    def write(physical, value):
        if physical >= capacity and unpopulated != "mirror":
            return
        ram[physical % capacity] = value

    previous = read(ANCHOR_PHYS)
    write(ANCHOR_PHYS, 0x5A)
    found_kib = None

    for candidate_kib in range(FIRST_KIB, 1024, 8):
        candidate_phys = ANCHOR_PHYS + candidate_kib * 1024
        assert candidate_phys < ROM_START
        saved = read(candidate_phys)
        valid = True
        for value in (0x55, 0xAA):
            write(candidate_phys, value)
            if read(candidate_phys) != value or read(ANCHOR_PHYS) != 0x5A:
                valid = False
                break
        write(candidate_phys, saved)
        if not valid:
            found_kib = candidate_kib
            break

    write(ANCHOR_PHYS, previous)
    assert ram == before, f"{kib} KiB ({unpopulated}): probe changed RAM"
    detected_kib = found_kib if found_kib is not None else 1024
    tpa_end = min(detected_kib * 1024, ROM_START) // 16
    return detected_kib, 0x0800, tpa_end - 0x0800


for kib in range(128, 1025, 8):
    for unpopulated in ("mirror", "ff", "zero"):
        detected, start, length = simulate(kib, unpopulated)
        expected = min(kib * 1024, ROM_START) // 16 - 0x0800
        assert (detected, start, length) == (kib, 0x0800, expected), (
            f"{kib} KiB / {unpopulated}: detected={detected}, "
            f"MRT=({start:#x},{length:#x}), expected length {expected:#x}"
        )

if len(sys.argv) > 1:
    data = Path(sys.argv[1]).read_bytes()
    assert len(data) == 0x1900, f"unexpected CBIOS size {len(data):#x}"
    assert bytes.fromhex("01 00 08 00 78 00") in data, "missing initial MRT entry"
print("PASS: 113 capacities (128..1024 KiB, 8 KiB steps) x mirror/FF/zero absent RAM; probe restores memory and sizes MRT")
