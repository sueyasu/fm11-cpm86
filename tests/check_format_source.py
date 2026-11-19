#!/usr/bin/env python3
"""Static ABI/geometry checks for FM-11 FORMAT.A86 (ASM86 is guest-only)."""
from pathlib import Path
import re

source = Path("command/FORMAT.A86").read_text(encoding="ascii")
instructions = "\n".join(line.split(";", 1)[0] for line in source.splitlines())
symbols = set(re.findall(r"^([A-Za-z_][A-Za-z_0-9]*):", source, flags=re.M))
refs = set(re.findall(r"^\s*(?:call|jmp|je|jne|jz|jnz|jc|jnc|ja|jae|jb|jbe|loop)\s+([a-z_][a-z_0-9]*)\b",instructions, flags=re.M|re.I))
missing = sorted(x for x in refs if x.lower() not in {s.lower() for s in symbols})
assert not missing, missing
assert len(re.findall(r"^end[ \t]*$", source, re.M|re.I)) == 1

# ASM86 symbol identifiers are case-insensitive: HDD_SECTOR EQU and
# hdd_sector DB cannot coexist, even if their case differs.
definitions = re.findall(
    r"^([A-Za-z_][A-Za-z_0-9]*)\\s*(?::|\\s+(?:equ|db|dw|dd|rs)\\b)",
    source, re.M | re.I,
)
normalized = [symbol.upper() for symbol in definitions]
assert len(normalized) == len(set(normalized)), (
    "ASM86 duplicate symbol definitions",
    sorted(symbol for symbol in set(normalized) if normalized.count(symbol) > 1),
)
assert "HDD_SECTOR     equ" not in source

assert not re.search(r"\[(?:si|di|bx|bp)\s*\+\s*\d+\]", instructions,re.I)
assert not re.search(r"\b(?:es|cs|ss|ds):\s*\[", instructions,re.I)
assert "mov     cl,Byte Ptr .080h" in source
assert "HD_DRIVE" not in source  # must use HDD_DRIVE consistently
assert "HDD_DRIVE      equ     8" in source
assert "cmp     al,'I'" in source
assert "cmp     ah,'D'" in source
assert "hdd_initialize:" in source
assert "hdd_result_wait:" in source
assert "hdd_sector_io:" in source
assert "mov     al,014h" in source
assert "mov     al,011h" in source
assert "mov     al,023h" in source
assert "mov     dx,0fdc0h" in source
assert "mov     dx,0fdc2h" in source
assert "mov     dx,014h" in source   # DMA2 address
assert "mov     dx,015h" in source   # DMA2 count
assert "mov     dx,022h" in source   # DMA2 bank
assert "mov     al,04ah" in source   # DMA2 memory -> device
assert "mov     al,6" in source      # DMA2 mask
assert "mov     al,2" in source      # DMA2 unmask
assert "mov     Word Ptr hdd_remaining,64" in source
assert "mov     Word Ptr hdd_cyl,0" in source
assert "mov     ax,0e5e5h" in source
assert "msg_hdd_options" in source
assert "INCLUDE FDIPL2D.INC" in source
assert "INCLUDE FDIPL2HD.INC" in source
assert "INCLUDE HDIPL.INC" in source
assert "hdd_install_system:" in source
assert "hdd_verify_system:" in source
assert "hdd_copy_to_sectorbuf:" in source
assert "hdd_compare_sector:" in source
assert "hdd_read_sector:" in source
assert "call    hdd_install_system" in source
assert "call    hdd_verify_system" in source
assert "call    hdd_sense" in source
assert "cmp     al,HDD_DRIVE" in source
assert "cmp     Byte Ptr mode,MODE_LOW" in source
assert "msg_hdd_system_done" in source
assert "mov     al,070h" in source  # binary LBA mode, same as CBIOS
assert "hdd_lba_shift:" in source
assert "rcl     dx,1" in source
assert "mov     Word Ptr hdd_remaining,64" in source
assert "mov     Word Ptr remaining,RES_SECTORS" in source
assert "mov     Word Ptr remaining,2" in source
assert source.count("call    hdd_write_sector") >= 3
assert source.count("call    hdd_read_sector") >= 3
for name in ("msg_title","msg_usage","msg_hdd_name","msg_hdd_options",
             "msg_hdd_install","msg_hdd_format","msg_hdd_error",
             "msg_hdd_system_done"):
    matches = re.findall(r"^" + name + r"\s+db\b", source, re.M | re.I)
    assert len(matches) == 1, f"missing or duplicated {name}"


# Check all nine known MDC geometries against original emulator constants.
geometries = (
    (0x04,157,4),(0x08,315,2),(0x05,157,6),
    (0x09,315,4),(0x0a,315,6),(0x0c,315,8),
    (0x14,747,4),(0x15,747,7),(0x16,747,11)
)
for dtype, cylinders, heads in geometries:
    assert f"cmp     al,0{dtype:02x}h" in source
    assert f"mov     Word Ptr hdd_cylinders,{cylinders}" in source
    assert f"mov     Byte Ptr hdd_heads,{heads}" in source
    # 32 sectors x 256 bytes, 16-KiB blocks. One cylinder reserved.
    blocks = ((cylinders-1)*heads*32*256)//16384
    assert 1 < blocks < 65536
    assert heads >= 2  # 16KiB directory fits at start of cylinder 1
assert max(c*h*32*256 for _,c,h in geometries) == 67313664
assert "call    floppy_position" in source
assert "positioned_drive db     0ffh" in source
assert "mov     al,00bh" in source
assert "mov     al,01bh" in source
assert "mov     Byte Ptr positioned_drive,0ffh" in source
assert source.rstrip("\r\n\x1a").endswith("end")
print("PASS: FORMAT A:..I:/HDD, nine MDC geometries, DMA2, directory and ASM86 source checks")
