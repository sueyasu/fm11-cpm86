# Embedded CBIOS self-test (FM-11 8088)

Use this to test the **actual CBIOS** without executing CCP/BDOS. The
self-test is assembled into the same CBIOS image and its INIT entry jumps
to the self-test instead of the CCP cold entry. The regular `make boot`
image and `build/cbios.bin` are unchanged.

## Build

Run from the repository root, with `nasm`, the original external
`external/system/cpm86_core.bin` and `external/commands/ASM86.CMD`
present:

```sh
git pull
make selftest
```

This creates:

- `build/cbios_selftest.bin` — 0x1900-byte CBIOS with embedded tests
- `build/fm11_cpm86_selftest_2d.img` — separate disposable 320 KiB disk
- `build/iplrom.bin` — same IPL ROM as the normal build

**The self-test performs a WRITE and RESTORE on logical track 79,
record 31. Never attach a valuable or original image.** Use only the
`_selftest_2d.img` image from the build target and retain a copy if
you intend to rerun it.

Run FM-11 SDL with the normal 8088 CPU-card configuration and ROM options,
but substitute the `_selftest_2d.img` for the ordinary CP/M-86 disk.
The usual IPL consumes an initial character to allow PTY attachment.
After it loads the resident image, the expected heading is:

```text
FM-11 CP/M-86 BIOS: serial initialized

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
