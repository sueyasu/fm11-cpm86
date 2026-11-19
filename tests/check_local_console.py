#!/usr/bin/env python3
"""Static regression of the FM-11 CP/M-86 local console and serial fallback.

This validates the source-level hardware command protocol, CBIOS ABI
selection, boot ROM startup gating, and local/serial binary dimensions.
It does NOT substitute for an emulator keyboard/display integration test.
"""
from pathlib import Path

cbios = Path("src/cbios.asm").read_text()
local = Path("src/cbios_local_console.inc").read_text()
hdd = Path("src/hdd_bootrom.asm").read_text()
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

for text, name in ((hdd, "HDD reset ROM"),):
    assert "%if CONSOLE_LOCAL = 0" in text, f"{name}: local boot still waits for PTY"
    assert "%endif" in text
    assert "%define CONSOLE_LOCAL 1" in text

for name in ("cbios_serial.bin", "hdd_bootrom_serial.bin"):
    assert name in makefile
assert "tests/check_local_console.py" in makefile

for name in ("cbios", "cbios_serial"):
    path = Path("build") / (name + ".bin")
    assert path.exists() and path.stat().st_size == 0x1900, name
for name in ("hdd_bootrom", "hdd_bootrom_serial"):
    path = Path("build") / (name + ".bin")
    assert path.exists() and path.stat().st_size == 0x1000, name

print("PASS: local FM-11 FD05/FC80 console ABI, key handling and serial fallback binaries")
