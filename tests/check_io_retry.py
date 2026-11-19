#!/usr/bin/env python3
"""Static regression for physical I/O retry paths (not a hardware test)."""
from pathlib import Path

bios = Path("src/cbios.asm").read_text()
hdd = Path("src/cbios_hdd.inc").read_text()
fdc = bios.split("fdc2d_transfer:", 1)[1].split('%include "src/cbios_hdd.inc"', 1)[0]
mdc = hdd.split("hdd_transfer:", 1)[1].split("hdd_cylinders dw", 1)[0]

for code, counter, limit, busy_check in (
    (fdc, "fdc_attempts", 10, "test al,0x02"),
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
print("PASS: bounded physical FDD/MDC retries and DMA reinitialization")
