#!/usr/bin/env python3
"""Static regression for runtime CP/M-86 IOBYTE CON routing.

Hardware/emulator integration remains a separate test.
"""
from pathlib import Path

source = Path("src/cbios.asm").read_text()
assert "jmp strict near GETIOBF" in source
assert "jmp strict near SETIOBF" in source
assert "GETIOBF:\n    mov al,[iobyte]" in source
assert "SETIOBF:\n    mov [iobyte],cl" in source

init = source.split("\nINIT:\n", 1)[1].split("\nWBOOT:\n", 1)[0]
assert "mov byte [iobyte],1" in init
assert "mov byte [iobyte],0" in init
assert init.index("mov byte [iobyte],1") < init.index("mov cx,BOOT_DRIVE")

for start, stop in (("CONST:", "CONIN:"), ("CONIN:", "CONOUT:"), ("CONOUT:", "LISTOUT:")):
    part = source.split("\n" + start + "\n", 1)[1].split("\n" + stop + "\n", 1)[0]
    assert "mov al,[iobyte]" in part, start
    assert "and al,3" in part, start
    assert "cmp al,1" in part and "cmp al,3" in part, start
    assert ".local:" in part, start

conin = source.split("\nCONIN:\n", 1)[1].split("\nCONOUT:\n", 1)[0]
assert "SER_RX_READY" in conin and "SER_DATA" in conin
assert "call local_conin" in conin
conout = source.split("\nCONOUT:\n", 1)[1].split("\nLISTOUT:\n", 1)[0]
assert "call local_putc" in conout
assert "call serial_putc" in conout
assert "call serial_putc_mirror" in conout
assert conout.index("call local_putc", conout.index(".mirror:")) < conout.index("call serial_putc_mirror")
assert "loop .wait" in source.split("\nserial_putc_mirror:\n", 1)[1].split("\nserial_puts:\n", 1)[0]
assert '%include "src/cbios_local_console.inc"' in source
assert source.count('%include "src/cbios_local_console.inc"') == 1
print("PASS: runtime IOBYTE TTY/CRT/UC1 console routing and bounded mirror")
