#!/usr/bin/env python3
"""Static and model checks for FM-11 CP/M-86 8 KiB RAM probing.

The model follows the emulator's 20-bit bus: missing RAM mirrors
modulo installed RAM bytes, while the last 4 KiB is read-only ROM.
The tests verify byte restoration and every 8 KiB capacity from
128 KiB through 1 MiB. They do not execute CBIOS instructions.
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
    "mov byte [es:RAM_PROBE_OFF],0xa5",
    "cmp byte [RAM_PROBE_OFF],0xa5",
    "mov [es:RAM_PROBE_OFF],dl",
    "add bx,0x0200",
    "loop .probe",
    "mov word [cs:mrt_tpa_len],0xf700",
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


def simulate(kib):
    capacity = kib * 1024
    ram = bytearray(capacity)
    # Initialize anchor and each candidate to different bytes,
    # including targets that wrap into earlier installed RAM.
    for physical in range(ANCHOR_PHYS, ROM_START, 0x2000):
        ram[physical % capacity] = (physical >> 13) & 0xFF
    before = ram[:]

    previous = ram[ANCHOR_PHYS]
    ram[ANCHOR_PHYS] = 0x5A
    found_kib = None

    for candidate_kib in range(FIRST_KIB, 1024, 8):
        candidate_phys = ANCHOR_PHYS + candidate_kib * 1024
        assert candidate_phys < ROM_START
        target = candidate_phys % capacity
        saved = ram[target]
        ram[target] = 0xA5
        alias = ram[ANCHOR_PHYS] == 0xA5
        ram[target] = saved
        if alias:
            found_kib = candidate_kib
            break

    ram[ANCHOR_PHYS] = previous
    assert ram == before, f"{kib} KiB: probe changed RAM contents"
    detected_kib = found_kib if found_kib is not None else 1024
    tpa_end = min(detected_kib * 1024, ROM_START) // 16
    return detected_kib, 0x0800, tpa_end - 0x0800


for kib in range(128, 1025, 8):
    detected, start, length = simulate(kib)
    expected = min(kib * 1024, ROM_START) // 16 - 0x0800
    assert (detected, start, length) == (kib, 0x0800, expected), (
        f"{kib} KiB: detected={detected}, MRT=({start:#x},{length:#x}), "
        f"expected length {expected:#x}"
    )

if len(sys.argv) > 1:
    data = Path(sys.argv[1]).read_bytes()
    assert len(data) == 0x1900, f"unexpected CBIOS size {len(data):#x}"
    assert bytes.fromhex("01 00 08 00 78 00") in data, "missing initial MRT entry"
print("PASS: 113 RAM capacities (128..1024 KiB, 8 KiB increments), safe ROM bounds, restored RAM and MRT")
