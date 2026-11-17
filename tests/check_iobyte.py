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
assert ".shared_wait:" in conin
assert "call local_const" in conin
assert "mov bl,al" in conin
assert "cmp byte [uc1_next],0" in conin
assert "mov byte [uc1_next],1" in conin
assert "mov byte [uc1_next],0" in conin
assert "call local_conin" in conin.split(".shared_local:",1)[1]
assert "in al,dx" in conin.split(".serial_read:",1)[1]
assert "uc1_next db 0" in source

const = source.split("\nCONST:\n",1)[1].split("\nCONIN:\n",1)[0]
assert ".shared:" in const
assert "call local_const" in const.split(".shared:",1)[1]
assert "SER_RX_READY" in const.split(".serial:",1)[1]
assert "call local_conin" in conin
conout = source.split("\nCONOUT:\n", 1)[1].split("\nLISTOUT:\n", 1)[0]
assert "call local_putc" in conout
assert "call serial_putc" in conout
assert "call serial_putc_mirror" in conout
assert conout.index("call local_putc", conout.index(".mirror:")) < conout.index("call serial_putc_mirror")
assert "loop .wait" in source.split("\nserial_putc_mirror:\n", 1)[1].split("\nserial_puts:\n", 1)[0]
assert '%include "src/cbios_local_console.inc"' in source
assert source.count('%include "src/cbios_local_console.inc"') == 1
print("PASS: runtime IOBYTE TTY/CRT/dual-input UC1 console routing and bounded mirror")
