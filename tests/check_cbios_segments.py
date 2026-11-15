#!/usr/bin/env python3
"""Keep CBIOS entry points independent of the calling program's DS."""
from pathlib import Path
import re

source = Path("src/cbios.asm").read_text()
start = source.index("\nHOME:\n") + 1
end = source.index("; CP/M-86 128-byte record I/O", start)
entry_points = source[start:end]
tail_start = source.index("\nGETIOBF:\n") + 1
tail_end = source.index("\nhello db", tail_start)
entry_points += source[tail_start:tail_end]

required = {
    "HOME": ("cur_track",),
    "SELDSK": ("cur_disk",),
    "SETTRK": ("cur_track",),
    "SETSEC": ("cur_sector",),
    "SETDMA": ("dma_off",),
    "SETDMAB": ("dma_seg",),
    "GETIOBF": ("iobyte",),
    "SETIOBF": ("iobyte",),
}
for name, variables in required.items():
    match = re.search(rf"(?m)^{name}:\s*$([\s\S]*?)(?=^\w[\w.]*:|\Z)", entry_points, re.M)
    assert match, f"Missing CBIOS entry point {name}"
    body = match.group(1)
    for var in variables:
        assert re.search(rf"\[cs:{var}(?:\+\w+)?\]", body), (
            f"{name} must access BIOS-owned {var} relative to CS, not caller DS"
        )
# SELDSK should not read the DPH address from an extra memory table.
# A:..D: have fixed descriptors in the current resident image.
sel_start = source.index("\nSELDSK:\n")
sel_end = source.index("\nSETTRK:\n", sel_start)
sel = source[sel_start:sel_end]
for n in range(4):
    assert re.search(rf"mov bx,dph{n}\b", sel), f"SELDSK must return dph{n} directly"
assert "mov bx,[cs:dph_table+bx]" not in sel
print("PASS CBIOS entry points use CS for BIOS-owned state and fixed DPH addresses")
