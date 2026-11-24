#!/usr/bin/env python3
"""Static regression of the FM-11 CP/M-86 local console and serial fallback.

This validates the source-level hardware command protocol, CBIOS ABI
selection, HDD disk IPL handoff, and local/serial CBIOS dimensions.
It does NOT substitute for an emulator keyboard/display integration test.
"""
from pathlib import Path

cbios = Path("src/cbios.asm").read_text()
local = Path("src/cbios_local_console.inc").read_text()
ipl_hdd = Path("src/ipl_hdd.asm").read_text()
makefile = Path("Makefile").read_text()

assert "%define CONSOLE_LOCAL 1" in cbios
assert "%define CONSOLE_LOCAL 0" in cbios
assert "%include \"src/cbios_local_console.inc\"" in cbios
assert "times 6 nop" in cbios, "cold-start boot-drive patch offset must not move"

init = cbios.split("\nINIT:\n", 1)[1].split("\nWBOOT:\n", 1)[0]
assert init.index("mov cx,BOOT_DRIVE") < init.index("call local_putc")
assert "mov byte [local_key_valid],0" in init
assert "mov byte [local_seq_count],0" in init
assert "mov al,0x16" in init and "mov al,0x0b" in init

const = cbios.split("\nCONST:\n", 1)[1].split("\nCONIN:\n", 1)[0]
conin = cbios.split("\nCONIN:\n", 1)[1].split("\nCONOUT:\n", 1)[0]
conout = cbios.split("\nCONOUT:\n", 1)[1].split("\nLISTOUT:\n", 1)[0]
assert "call local_const" in const
assert "call local_conin" in conin
assert "call local_putc" in conout
assert "call serial_putc" in conout
assert "jmp CONIN" in cbios

for item in (
    "SUB_CPU_CTRL equ 0xFD05",
    "SUB_MAILBOX  equ 0xFC80",
    "SUB_CHAROUT  equ 0x12",
    "SUB_INKEY2   equ 0x2D",
    "mov al,0x80",
    "out dx,al",
    "mov dx,SUB_MAILBOX",
    "mov al,bl",
    "mov al,bh",
    "mov dx,SUB_MAILBOX+3",
    "mov byte [local_key_valid],1",
    "mov byte [local_seq_first],'['",
    "mov al,0x1b",
    "cmp al,0x14",
    "cmp al,0x16",
    "cmp al,0x17",
    "cmp al,0x18",
    "cmp al,0x19",
    "mov al,0x7f",
):
    assert item in local, f"missing local console feature: {item}"

assert local.count("mov byte [local_seq_count],2") == 1
assert "local_poll:" in local
assert "local_const:" in local
assert "local_conin:" in local

# The current HDD boot path loads the 512-byte on-disk IPL, then
# transfers control to CBIOS. It no longer builds a separate HDD reset ROM.
assert 'org 0' in ipl_hdd
assert 'jmp 0x0400:0x2500' in ipl_hdd
assert 'src/ipl_hdd.asm' in makefile
assert 'src/hdd_bootrom.asm' not in makefile
assert 'hdd_bootrom_serial.bin' not in makefile
assert '$(BUILD)/cbios_serial.bin:' in makefile
assert '$(BUILD)/cbios_hdd.bin:' in makefile
assert "tests/check_local_console.py" in makefile

for name in ("cbios", "cbios_serial", "cbios_hdd"):
    path = Path("build") / (name + ".bin")
    assert path.exists() and path.stat().st_size == 0x1900, name
ipl_path = Path("build/ipl_hdd.bin")
assert ipl_path.exists() and ipl_path.stat().st_size == 512

print("PASS: local FD05/FC80 console ABI, HDD IPL handoff and CBIOS variants")
