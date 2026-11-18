#!/usr/bin/env python3
"""Check the common CP/M-86 SYNC.A86 guest command's cache ABI."""
from pathlib import Path
import re

source = Path("command/SYNC.A86").read_text(encoding="ascii").replace("\r\n", "\n")
bios = Path("src/cbios.asm").read_text()
assert "CACHE_SYNC_OFS  EQU     03DD8h" in source
assert "BIOS_SYS_SEG    EQU     0400h" in source
assert "CACHE_SYNC_OFS  equ 0x3DD8" in bios
assert re.search(r"bios_cache_sync:\s+DB\s+09Ah\s+DW\s+CACHE_SYNC_OFS\s+DW\s+BIOS_SYS_SEG\s+ret", source, re.I)
assert re.search(r"start:\s+call\s+bios_cache_sync\s+jnc\s+sync_ok", source, re.I)
assert "mov     dx,offset msg_failed" in source
assert "mov     dx,offset msg_ok" in source
assert re.search(r"exit_program:\s+mov\s+cl,0\s+int\s+BDOSINT", source, re.I)
assert "call    puts" in source
assert "DSEG\n        ORG     100h" in source
assert source.rstrip("\r\n\x1a").endswith("END")
assert "CACHE_RESET_OFS" not in source
print("PASS: common SYNC.A86 uses PC-98/FM-11 0400:3DD8 CACHE_SYNC ABI and checks CF")
