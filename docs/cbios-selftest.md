# Embedded CBIOS self-test (FM-11 8088)

Use this to test the **actual CBIOS** without executing CCP/BDOS. The self-test replaces the CCP/BDOS core region (0x2500 bytes) in a disposable
image, while the *real CBIOS remains 0x1900 bytes*. Its INIT entry jumps
back to the self-test instead of the CCP cold entry. The regular `make boot-2d`
image and `build/cbios.bin` are unchanged.

## Build

Run from the repository root, with `nasm`, `external/commands/ASM86.CMD` present. The normal external CP/M-86 core
is **not required** for this diagnostic:

```sh
git pull
make selftest
```

This creates:

- `build/cbios_selftest_core.bin` — 0x2500-byte diagnostic replacement core
- `build/cbios_selftest.bin` — 0x1900-byte CBIOS, INIT redirects to test core
- `build/fm11_cpm86_selftest_2d.d88` and `.raw` — disposable disk images with the standard 512-byte disk IPL

**The self-test performs a WRITE and RESTORE on logical track 79,
record 31. Never attach a valuable or original image.** Use only the
`_selftest_2d.d88` image from the build target and retain a copy if
you intend to rerun it.

Run FM-11 SDL with the normal 8088 CPU-card configuration and ROM options,
but substitute the `_selftest_2d.d88` for the ordinary CP/M-86 disk.
Use the original FM-11 2D floppy boot ROM. Connect the serial terminal
before booting; the disk IPL does not wait for an initial character.
After it loads the resident image, the expected heading is:

```text
CP/M-86 v1.1 for FM-11 series

        RAM ...KiB / TPA ...KiB

CBIOS SELFTEST (NO CCP/BDOS)
```

The test checks the console status and output vectors, IOBYTE,
SELDSK DPH/DPB pointers, HOME, SETTRK, SETSEC, SETDMA, SETDMAB,
SECTRAN, GETSEGT, invalid track/record errors, and reads the
first directory record (expected `ASM86.CMD`). It then prints:

```text
Press one key for CONIN test:
```

Type a single character. The test checks CONIN and then runs a
128-byte disk WRITE, READ-back verification, and restoration of the
saved original record. Success ends with:

```text
PASS WRITE/READ/RESTORE
PASS CBIOS SELFTEST
```

The program stops with `HLT`; no CCP prompt is expected.

A `FAIL` means the self-test did not pass. In the write-test phase it
attempts to restore the saved record even on failure. If restoration
fails, **do not reuse the disk image**.

WBOOT is not invoked, because its current implementation jumps to the
CCP warm entry. READER is not independently exercised (it jumps to
CONIN); LISTST currently always returns FFh. These limitations do
not make this an end-to-end CP/M-86 test.

This test depends on NASM assembly and an emulator run. A successful
image layout check alone does **not** prove runtime PASS.

## Track 80 branch trace (Linux 8088 investigation)

After the stand-alone `main8088_cmp_jae` test passed but the complete
CBIOS self-test reported `FAIL READ track=80 returned AX=0000`, the
self-test-only build gained minimally invasive trace slots. The normal
`build/cbios.bin` and production disk image are unaffected.

Rebuild and run the disposable self-test image as before:

```sh
git pull
make selftest
```

When the track 80 check fails, the extended output is:

```text
FAIL READ track=80 returned AX=xxxx TARGET=ssss:oooo CODE=hhhhhhhh ENTRY=xx DS=xxxx BX=xxxx FLAGS=xxxx PATH=xx DONE_AX=xxxx
```

Fields:
- `AX`: the caller-visible return status.
- `TARGET`: CS:offset of the actual READ label used by the assembler.\n- `CODE`: four bytes read from that CS:offset immediately before CALL.\n  In the instrumented build the READ entry should begin with a CS-prefixed\n  store (`2E C6 ...`). `00` or `FF` bytes here point to an image/layout\n  problem rather than a conditional-branch error.\n- `ENTRY`: CS-relative stage marker: `00` = READ entry not reached,
  `01` = READ entered but common entry not reached, `02` = common
  entry reached but prologue incomplete, `03` = prologue completed.
- `DS`: segment recorded with a CS override after segment setup;
  expected `0400`. This value is independent of the current DS.
- `BX`: the value of `cur_track` actually loaded inside READ before CMP.
- `FLAGS`: saved immediately after `CMP BX,80` (CF=bit 0, ZF=bit 6).
  For BX=0050h, expected CF=0 and ZF=1.
- `PATH`: `01` = comparison reached but no branch landing observed,
  `02` = `.invalid` branch executed, `03` = `.valid` branch executed,
  `00` = comparison never reached.
- `DONE_AX`: AX at READ's shared epilogue, before POPs/RET.
  For an invalid track it should be 0001h.

This trace captures data with MOV and PUSHF/POP memory, which preserve
the CMP condition flags used by JAE. It does not modify the BIOS
control flow or log to the serial port from within READ.

Interpreting an anomaly: `BX=0050 FLAGS=004x PATH=03` would implicate
the conditional branch or address decoding; `PATH=02 DONE_AX=0001
AX=0000` would implicate stack/return or post-return behavior.
Any different BX means the track state changed between caller and READ.

Unlike the earlier BX/FLAGS/PATH fields, ENTRY and DS are recorded with
explicit CS segment overrides. This distinguishes a CALL/JMP/prologue
problem from an incorrect DS base. The normal CBIOS image is unchanged.

For this follow-up the self-test sets AX=5A5Ah immediately before the
track-80 CALL. The invalid-track result must still be AX=0001h. If the
callee is never entered, an unchanged 5A5Ah distinguishes that from a
function which partly executes. Compare TARGET and CODE first, then the
ENTRY marker and the internal flags.
