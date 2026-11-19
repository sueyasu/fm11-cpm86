#!/usr/bin/env python3
"""Validate PC-98 compatible private cache FAR ABI in FM-11 CBIOS binaries.

Four-byte stubs must remain at resident 0400:3DD8 and 0400:3DDC.
The underlying near CALL targets are verified as in-image code, and
the FORMAT source must use the matching 9Ah FAR CALL encoding.
"""
from pathlib import Path
import re
import sys

BASE = 0x2500
BIOS_SIZE = 0x1900
SYNC = 0x3DD8
RESET = 0x3DDC
bios_source = Path("src/cbios.asm").read_text()
format_source = Path("command/FORMAT.A86").read_text(encoding="ascii")

assert "CACHE_SYNC_OFS  equ 0x3DD8" in bios_source
assert "CACHE_RESET_OFS equ 0x3DDC" in bios_source
assert "times (CACHE_SYNC_OFS - 0x2500) - ($ - bios_start) db 0" in bios_source
assert "call CACHE_SYNC\n    retf\n    call CACHE_RESET\n    retf" in bios_source
assert "WBOOT:\n" in bios_source
wboot = bios_source.split("WBOOT:", 1)[1].split("CONST:", 1)[0]
assert re.search(r"call CACHE_SYNC\s+jc \.sync_failed\s+jmp 0x0006", wboot)
failure = wboot.split(".sync_failed:", 1)[1]
assert re.search(r"push cs\s+pop ds\s+cld", failure)
assert "mov byte [ansi_state],0" in failure
assert "mov si,wboot_sync_error_msg" in failure
assert re.search(r"lodsb\s+test al,al\s+jz \.stop\s+mov cl,al\s+call CONOUT", failure)
assert re.search(r"\.stop:\s+cli\s+\.halt:\s+hlt\s+jmp \.halt", failure)
assert "wboot_sync_error_msg db 13,10,'WBOOT: disk cache write-back failed. System halted.',13,10,0" in bios_source

sync_body = bios_source.split("\nCACHE_SYNC:\n", 1)[1].split("\nCACHE_RESET:\n", 1)[0]
reset_body = bios_source.split("\nCACHE_RESET:\n", 1)[1].split("\n; Keep the same", 1)[0]
for body in (sync_body, reset_body):
    for fragment in ("push ds", "push cs", "pop ds", "call cache_flush_all", "pop ds", "ret"):
        assert fragment in body, fragment
assert "call cache_invalidate" in reset_body
assert reset_body.index("jc .failed") < reset_body.index("call cache_invalidate")
assert "clc" in reset_body

assert "CACHE_RESET_OFS equ     03ddch" in format_source
assert re.search(
    r"confirmed:\s+call\s+crlf\s+;[^\n]*\n(?:[^\n]*\n)*?"
    r"\s*call\s+bios_cache_reset\s+jnc\s+fmt_cache_ready"
    r"\s+jmp\s+cache_reset_failed", format_source, re.I
)
helper = format_source.split("bios_cache_reset:\n", 1)[1].split("\nputs:", 1)[0]
assert re.search(
    r"DB\s+09Ah\s+DW\s+CACHE_RESET_OFS\s+DW\s+BIOS_SEG\s+ret",
    helper, re.I,
)
assert "msg_cache_error" in format_source
error_path = format_source.split("cache_reset_failed:\n", 1)[1].split("\nreset_exit:", 1)[0]
assert "jmp     exit_program" in error_path
assert "int     BDOSINT" not in error_path
assert format_source.index("call    bios_cache_reset") < format_source.index("call    find_source")
assert format_source.index("call    bios_cache_reset") < format_source.index("call    hdd_initialize")
assert format_source.index("call    bios_cache_reset") < format_source.index("call    initialize_media")

for filename in sys.argv[1:]:
    data = Path(filename).read_bytes()
    assert len(data) == BIOS_SIZE, (filename, len(data))
    for entry, label in ((SYNC, "SYNC"), (RESET, "RESET")):
        idx = entry - BASE
        stub = data[idx:idx + 4]
        assert stub[0] == 0xE8 and stub[3] == 0xCB, (
            filename, label, stub.hex()
        )  # near CALL relative16 + FAR RET
        distance = int.from_bytes(stub[1:3], "little", signed=True)
        destination = idx + 3 + distance
        assert 0 <= destination < SYNC - BASE, (
            filename, label, destination
        )
    assert data[RESET - BASE + 4:] == bytes(BIOS_SIZE - (RESET - BASE + 4)), (
        filename, "unexpected content after ABI stubs"
    )

print("PASS: PC-98-compatible 0400:3DD8/3DDC FAR ABI, DS/CF discipline and FORMAT reset call")
