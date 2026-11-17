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
assert source.rstrip().endswith("end\n\x1a".rstrip())
print("PASS: FORMAT A:..I:/HDD, nine MDC geometries, DMA2, directory and ASM86 source checks")
