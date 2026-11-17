#!/usr/bin/env python3
"""Check FM-11 CP/M-86 physical RAM probing and MRT size calculation.

The RAM model matches the configurable FM-11 8088 bus: a fixed 20-bit
address space, with each non-existent RAM address mirrored modulo the
installed RAM capacity.  The reset ROM is mapped at physical FF000h.
This is a deterministic model/static regression, NOT an emulator boot.
"""
from pathlib import Path
import sys

source = Path("src/cbios.asm").read_text()
init = source.split("\nINIT:\n", 1)[1].split("\nWBOOT:\n", 1)[0]
assert "call init_mrt" in init
assert init.index("call init_mrt") < init.index("jmp 0x0000")
section = source.split("\ninit_mrt:\n", 1)[1].split("\nGETIOBF:\n", 1)[0]
assert "mov bx,0x2400" in section
assert "mov cx,7" in section
assert "add bx,0x2000" in section
assert "loop .probe" in section
assert "mov byte [ram_probe_anchor],0x5a" in section
assert "mov byte [es:ram_probe_anchor],0xa5" in section
assert "mov dl,[es:ram_probe_anchor]" in section
assert "mov [es:ram_probe_anchor],dl" in section
assert "mov [ram_probe_anchor],si" in section
assert "mov word [mrt_tpa_len],0xf700" in section
assert "sub bx,0x0c00" in section
assert "mov [mrt_tpa_len],bx" in section
assert source.index("mrt_tpa_len:") < source.index("ram_probe_anchor:")
assert "dw 0x0800\nmrt_tpa_len:\n    dw 0x7800" in source

# Use the BIOS resident region as the exact logical offset being tested.
# A candidate is physical 04000h+offset+n*20000h.
ANCHOR_OFFSET = 0x3900
ANCHOR_PHYS = 0x4000 + ANCHOR_OFFSET
ROM_BASE = 0xFF000


def simulate(kib):
    ram = bytearray(kib * 1024)
    # Start with an arbitrary anchor value and nonuniform scratch values.
    for i in range(len(ram)):
        if i % 0x1000 == 0x900:
            ram[i] = (i >> 12) & 255
    original = ram[:]
    previous = ram[ANCHOR_PHYS]
    ram[ANCHOR_PHYS] = 0x5A
    found = None
    for number in range(1, 8):
        candidate_phys = ANCHOR_PHYS + number * 0x20000
        assert candidate_phys < ROM_BASE
        target = candidate_phys % len(ram)
        old = ram[target]
        ram[target] = 0xA5
        aliased = ram[ANCHOR_PHYS] == 0xA5
        ram[target] = old
        if aliased:
            found = number
            break
    ram[ANCHOR_PHYS] = previous
    assert ram == original, f"{kib} KiB: RAM contents changed after probe"
    detected_kib = found * 128 if found is not None else 1024
    tpa_start = 0x0800
    tpa_end = (detected_kib * 1024) // 16
    if detected_kib == 1024:
        tpa_end = 0xFF00  # upper 4 KiB read-only boot ROM
    return detected_kib, tpa_start, tpa_end - tpa_start


expected = {
    128: 0x1800,
    256: 0x3800,
    384: 0x5800,
    512: 0x7800,
    640: 0x9800,
    768: 0xB800,
    896: 0xD800,
    1024: 0xF700,
}
for kib, paragraphs in expected.items():
    detected, start, length = simulate(kib)
    assert (detected, start, length) == (kib, 0x0800, paragraphs), (
        kib, detected, start, hex(length)
    )

if len(sys.argv) > 1:
    data = Path(sys.argv[1]).read_bytes()
    assert len(data) == 0x1900
    # Default in-memory table image is 1 region, segment 0800h, 7800h
    # paragraphs (512 KiB fallback, overwritten during INIT).
    default_table = bytes.fromhex("01 00 08 00 78 00")
    assert default_table in data, "missing initial MRT entry"
print("PASS: RAM alias probe is restorable, and MRT covers all eight RAM sizes")
