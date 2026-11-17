#!/usr/bin/env python3
"""Static contracts for two 8 KiB FM-11 CP/M-86 track cache windows."""
from pathlib import Path

bios=Path("src/cbios.asm").read_text()
cache=Path("src/cbios_track_cache.inc").read_text()
test=Path("src/cbios_selftest.inc").read_text()

assert '%include "src/cbios_track_cache.inc"' in bios
assert "call cache_init" in bios
assert "call cache_ensure" in bios
assert "call cache_mark_dirty" in bios
assert "call cache_flush_all" in bios
assert "call cache_invalidate" in bios
assert "cache_segments dw 0,0" in cache
assert "cache_valid dw 0,0,0,0" in cache
assert "cache_dirty dw 0,0,0,0" in cache
assert "mov [mrt_tpa_len],ax" in cache
assert "sub ax,0x0400" in cache

# Record translation and both read/write transfer directions
assert "mov cl,7" in bios
assert "shl bx,cl" in bios
# The READ half switches DS from BIOS to its upper-memory cache.
# DMA variables must be explicitly CS-relative after that switch.
read_path = bios.split("; READ: track cache -> caller's 128-byte DMA record.",1)[1].split(".write_record:",1)[0]
assert "mov ds,ax" in read_path
assert "mov di,[cs:dma_off]" in read_path
assert "mov ax,[cs:dma_seg]" in read_path
assert "mov di,[dma_off]" not in read_path
for name in ("cache_select:", "cache_ensure:", "cache_bit:",
             "cache_copy_in:", "cache_copy_out:", "cache_flush_window:",
             "cache_flush_all:", "cache_mark_dirty:"):
    assert name in cache, name
for item in ("[cur_disk]", "[cur_track]", "[cur_sector]",
             "[cache_drive+si]", "[cache_track+bx]"):
    assert item in cache, item
for name in ("call fdc2d_read", "call hdd_read",
             "call fdc2d_write", "call hdd_write"):
    assert name in cache, name

# WRITE backs are deferred except for CP/M directory commits and eviction.
write_path=bios.split(".write_record:",1)[1].split(".success:",1)[0]
assert "rep movsw" in write_path
assert "call cache_mark_dirty" in write_path
assert "cmp byte [cache_write_type],1" in write_path
assert "call cache_flush_all" in write_path
assert "call sector_physical_write" in cache.split("cache_flush_window:",1)[1]
assert "jc .fail" in cache.split("cache_flush_window:",1)[1]
assert "and [cache_dirty+di],ax" in cache.split("cache_flush_window:",1)[1]

# Failures must not silently discard dirty windows.
assert "call cache_flush_window" in cache.split("cache_select:",1)[1]
assert "jc .failure" in cache.split("cache_select:",1)[1]
assert "call cache_flush_all" in bios.split("WBOOT:",1)[1]
assert "call cache_flush_all" in bios.split("SELDSK:",1)[1]
assert "fdc2d_buffer: times 256 db 0" in bios
assert "times BIOS_SIZE - ($ - bios_start) db 0" in bios
assert "cache_phys_reads" in test
assert "cache_phys_writes" in test
assert "cache_flush_all" in test
print("PASS: two-window 8 KiB write-back track cache; dirty flush and 128-byte record mapping")
