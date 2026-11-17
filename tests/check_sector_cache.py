#!/usr/bin/env python3
"""Static contracts for FM-11 CP/M-86 128-to-256-byte deblocking.

The actual transport executes on an 8088 and is exercised by CBIOS's
optional integration self-test; these checks catch accidental violations
of write-through and cache-key/invalidation requirements.
"""
from pathlib import Path

bios = Path("src/cbios.asm").read_text()
cache = Path("src/cbios_sector_cache.inc").read_text()
test = Path("src/cbios_selftest.inc").read_text()

assert '%include "src/cbios_sector_cache.inc"' in bios
assert "call cache_ensure" in bios
assert "call sector_physical_write" in bios
assert "call cache_invalidate" in bios
assert "mov byte [cache_valid],0" in bios
assert "cache_valid db 0" in cache

# Two 128-byte logical records must resolve to one 256-byte physical
# record; the cache key includes every physical identity dimension.
for source in (bios, cache):
    assert "shr bx,1" in source
for item in ("[cache_drive]", "[cache_track]", "[cache_sector]",
             "[cur_disk]", "[cur_track]", "[cur_sector]"):
    assert item in cache, item
for item in ("call fdc2d_read", "call hdd_read",
             "call fdc2d_write", "call hdd_write"):
    assert item in cache
assert "cache_valid],1" in cache
assert "jc .done" in cache

# Write-through: an unsuccessful physical commit must never leave a
# misleading valid cached sector or return success.
write_path = bios.split(".write_half:", 1)[1].split(".success:", 1)[0]
assert "rep movsw" in write_path
assert "call sector_physical_write" in write_path
assert "call cache_invalidate" in write_path
assert "jmp .error" in write_path
assert "call cache_ensure" in bios.split(".valid:", 1)[1].split(".copy_record:", 1)[0]

# The 256-byte buffer remains both DMA bounce and logical cache.
assert "fdc2d_buffer: times 256 db 0" in bios
assert "times BIOS_SIZE - ($ - bios_start) db 0" in bios
# Integration test will validate actual physical I/O reduction.
assert "cache_phys_reads" in test
assert "cache_phys_writes" in test
print("PASS: 128/256-byte deblocking, shared physical I/O, cache keys and write-through")
