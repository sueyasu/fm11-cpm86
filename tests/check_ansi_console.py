#!/usr/bin/env python3
"""Static/source regression for FM-11 ANSI console translation.

The CBIOS binaries are assembled and layout-checked separately by make test.
Visual behavior still needs a guest/emulator integration test.
"""
from pathlib import Path

bios = Path("src/cbios.asm").read_text()
local = Path("src/cbios_local_console.inc").read_text()
ansi = Path("src/cbios_ansi.inc").read_text()
mk = Path("Makefile").read_text()

assert '%include "src/cbios_ansi.inc"' in bios
assert "src/cbios_ansi.inc" in mk
assert "local_putc:\n    jmp ansi_putc" in local
assert "local_native_putc:" in local
assert "ansi_raw:\n    call local_native_putc" in ansi
assert "call local_putc" in bios.split("\nCONOUT:\n", 1)[1].split("\nLISTOUT:\n", 1)[0]
assert "call serial_putc_mirror" in bios
assert "mov byte [ansi_state],0" in bios.split("\nINIT:\n",1)[1].split("\nWBOOT:\n",1)[0]

# Preserve caller registers and FLAGS except the private transport CF.
entry = ansi.split("\nansi_putc:\n",1)[1].split("\n; Raw native output:",1)[0]
for instruction in ("pushf", "push ax", "push bx", "push cx", "push dx",
                    "push si", "push di", "push bp", "pop bp", "pop di", "pop si", "pop dx",
                    "pop cx", "pop bx", "pop ax", "popf"):
    assert instruction in entry, instruction

for operation in (".up:",".down:",".right:",".left:",
                  ".nextn:",".prevn:",".position:",".column:",".row:",
                  ".erase_display:",".erase_line:",".erase_chars:",
                  ".sgr:",".save:",".restore:",".reset:",".index:",
                  ".reverse_index:",".next_line:",".native_esc:"):
    assert operation in entry, operation

assert "mov al,0x12" in ansi and "call ansi_goto" in ansi
assert "mov al,'T'" in ansi and "mov al,'Y'" in ansi
assert "mov al,'*'" in ansi and "mov al,'G'" in ansi
assert "ansi_color_map db 0,2,4,6,1,3,5,7" in ansi
for param in ("cmp al,1", "cmp al,5", "cmp al,7",
              "cmp al,22", "cmp al,25", "cmp al,27",
              "cmp al,39", "cmp al,30", "cmp al,37",
              "cmp al,90", "cmp al,97"):
    assert param in ansi
assert ".clear1loop:" in ansi and ".line_all:" in ansi
assert "ansi_work_row db 1" in ansi and "ansi_work_col db 1" in ansi
assert "ansi_iter db 1" in ansi
assert "ANSI_MAX_PARAMS equ 8" in ansi
assert "mov al,255" in ansi
assert "jc ansi_putc.failed" in ansi
assert "mov sp,bp" in ansi
print("PASS: local ANSI/VT100 parser, native FM-11 control mapping, preserved serial routing")
