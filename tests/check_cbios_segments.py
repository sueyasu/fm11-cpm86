#!/usr/bin/env python3
"""Assert the original CP/M-86 BIOS calling convention is preserved.

The FM-11 BIOS follows the source PC-98 CBIOS: INIT establishes DS=CS,
and BIOS entry points use DS-relative work variables and DPH pointers.
This test deliberately does not 'fix' such references by adding CS:
overrides; an integration bug must be diagnosed in the emulator instead.
"""
from pathlib import Path
import re

source = Path("src/cbios.asm").read_text()
init = source.split("\nINIT:\n", 1)[1].split("\nWBOOT:\n", 1)[0]
assert re.search(r"mov ax,cs\s+mov ss,ax\s+mov sp,BIOS_STACK\s+mov ds,ax", init)

required = {
    "HOME": ["mov word [cur_track],0"],
    "SELDSK": ["mov bx,[dph_table+bx]", "mov [cur_disk],cl"],
    "SETTRK": ["mov [cur_track],cx"],
    "SETSEC": ["mov [cur_sector],cx"],
    "SETDMA": ["mov [dma_off],cx"],
    "SETDMAB": ["mov [dma_seg],cx"],
    "GETIOBF": ["mov al,[iobyte]"],
    "SETIOBF": ["mov [iobyte],cl"],
}
for name, lines in required.items():
    match = re.search(rf"(?m)^{name}:\s*$([\s\S]*?)(?=^[A-Z][A-Z0-9_]*:|\Z)", source, re.M)
    assert match, f"missing CBIOS entry point {name}"
    for line in lines:
        assert line in match.group(1), f"{name}: original ABI changed: {line}"
print("PASS: original CBIOS DS-relative ABI and DPH table lookup preserved")
