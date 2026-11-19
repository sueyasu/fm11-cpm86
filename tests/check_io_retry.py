#!/usr/bin/env python3
"""Static regression for physical I/O retry paths (not a hardware test)."""
from pathlib import Path

bios = Path("src/cbios.asm").read_text()
hdd = Path("src/cbios_hdd.inc").read_text()
fdc = bios.split("fdc2d_transfer:", 1)[1].split('%include "src/cbios_hdd.inc"', 1)[0]
mdc = hdd.split("hdd_transfer:", 1)[1].split("hdd_cylinders dw", 1)[0]

for code, counter, limit, busy_check in (
    (fdc, "fdc_attempts", 10, "test al,0x03"),
    (mdc, "hdd_attempts", 3, "test al,0x80"),
):
    assert f"mov byte [{counter}],{limit}" in code
    retry, attempt = code.split(".retry:", 1)[1].split(".attempt:", 1)
    assert "call .attempt" in retry
    assert "jc .retry_failed" in retry
    assert f"dec byte [{counter}]" in retry
    assert "jz .give_up" in retry
    assert busy_check in retry
    assert "jmp .bad" in retry
    assert "mov dx,0x1c" in attempt   # reprogram DMA on every attempt
    assert "mov dx,0x18" in attempt   # clear/check DMA terminal count
    finish = attempt.split(".finish:", 1)[1].split(".bad:", 1)[0]
    assert "pushf" in finish and "popf" in finish and "ret" in finish
    assert "stc" in attempt.split(".bad:", 1)[1]
assert "push cx\n    call .attempt\n    pop cx" in fdc
assert "jz .retry" in fdc
assert "jnz .retry" in mdc
# Type I positioning precedes every physical READ/WRITE attempt, with DMA
# masked. The cached physical cylinder belongs to the drive, not controller.
seek = bios.split("fdc_seek:", 1)[1].split("fdc_type1:", 1)[0]
assert "fdc_cylinder: times 8 db 0xff" in bios
assert "call fdc_position_index" in seek
assert "mov al,[fdc_cylinder+si]" in seek
assert seek.index("mov al,0x0b") < seek.index("mov al,0x1b")
assert "cmp al,ch" in seek and "mov [fdc_cylinder+si],ch" in seek
assert "mov byte [fdc_cylinder+si],0xff" in fdc
assert fdc.index("out dx,al\n    call fdc_seek") < fdc.index("mov dx,0x1c")
assert "test al,1" in bios.split("fdc_wait_idle:", 1)[1]
cache = Path("src/cbios_track_cache.inc").read_text()
assert cache.count("jmp fdc_forget_all") == 2
print("PASS: bounded physical FDD/MDC retries, DMA reinitialization and per-drive SEEK contracts")
