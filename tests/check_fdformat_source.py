#!/usr/bin/env python3
"""Static checks for the ASM86-only FM-11 FDFORMAT command.

ASM86/GENCMD run in CP/M-86, and therefore are not part of Linux CI.
These checks guard the source's drive mapping, IPL includes, and labels;
they are not a substitute for an actual ASM86 assembly or runtime test.
"""
from pathlib import Path
import re

source = Path("command/FDFORMAT.A86").read_text(encoding="ascii")
required = (
    "INCLUDE FDIPL2D.INC",
    "INCLUDE FDIPL2HD.INC",
    "fdipl2d_template",
    "fdipl2hd_template",
    "sectors_per_side,16",
    "sectors_per_side,26",
    "io_channel,0",
    "io_channel,1",
    "io_size,128",
    "io_size,256",
    "format_transfer",
    "build_format_track",
    "physical_dma_transfer",
    "FMT_TRACK2D",
    "FMT_TRACK2HD",
    "track_area",
)
for token in required:
    assert token.lower() in source.lower(), f"FDFORMAT.A86 missing {token}"
assert "int     01bh" not in source.lower(), "PC-98 ROM BIOS call leaked into FM-11"
instructions = "\n".join(line.split(";", 1)[0] for line in source.splitlines())
assert not re.search(r"\b(?:es|cs|ss|ds):\s*\[", instructions, re.I), ("ASM86 1.1 rejects MASM-style segment-register colon brackets")
# ASM86 uses a leading dot for a direct memory reference. Without it,
# 080h becomes an immediate length of 128 rather than the CP/M basepage.
assert "mov     cl,Byte Ptr .080h" in source
assert "mov     cl,Byte Ptr 080h" not in source
assert "mov     bx,BDOS_CURDRV" in source
assert "mov     al,[bx]" in source
assert "Byte Ptr [BDOS_CURDRV]" not in source
assert "mov     Byte Ptr dma_command,0f0h" in source
assert "msg_low_unsupported" not in source
assert source.rstrip().endswith("end\n\x1a".rstrip()), "ASM86 source must have END and Ctrl-Z"
definitions = set(re.findall(r"^([A-Za-z_][\w]*):", source, re.M | re.I))
references = re.findall(
    r"^\s*(?:CALL|JMP|JE|JNE|JZ|JNZ|JC|JNC|JA|JAE|JB|JBE|LOOP)\s+"
    r"([A-Za-z_][\w]*)", source, re.M | re.I)
missing = sorted(set(ref.lower() for ref in references)
                 - set(label.lower() for label in definitions))
assert not missing, f"unresolved FDFORMAT labels: {missing}"
assert len(references) >= 100
print("PASS: FM-11 FDFORMAT eight-drive references and ASM86 branch labels")
