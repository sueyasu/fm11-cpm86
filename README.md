# FM-11 CP/M-86 v1.1 port

This project is an initial port of CP/M-86 to the Fujitsu FM-11's 8088
main CPU card (or NEC V20 replacement). A first-stage 2D IPL ROM and
image builder are available. **The 2D boot to the A> prompt and empty DIR\nhave been verified in the emulator.**

## Fixed drive mapping and native 2HD boot

The CBIOS uses a fixed eight-drive map, independent of the boot device:

| CP/M drive | Controller | Physical drive |
|---|---|---|
| A:..D: | Mini-FDC 2D, 8237 DMA channel 0 | units 0..3 |
| E:..H: | Standard FDC 2HD, 8237 DMA channel 1 | units 0..3 |

The 2D boot image starts on **A:**; the 2HD boot image starts on
**E:**. All eight DPHs are available in either CBIOS build. Both
controllers read/write 256-byte sectors, deblocked into 128-byte CP/M
records with immediate read-modify-write on half-sector writes.

```sh
make boot-d88    # 2D bootable D88, boot drive A:
make boot-2hd    # 2HD bootable D88, boot drive E:
make test        # static / synthetic-disk tests; no CP/M core required
```

Both boot targets require `external/system/cpm86_core.bin` (0x2500
bytes) and include optional CP/M 8.3 files from `external/commands/`.
The new 2HD target produces:

- `build/cbios_2hd.bin`: 0x1900-byte CBIOS with cold-start drive E:
- `build/ipl_2hd.bin`: 512-byte disk IPL
- `build/fm11_cpm86_boot_2hd.raw`: 77 x 2 x 26 x 256-byte slot image
- `build/fm11_cpm86_boot_2hd.d88`: native FM-11 2HD boot image

In the D88 file, C0/H0 has 26 **128-byte FM** records and the
remaining side-tracks have 26 **256-byte MFM** records. The resident
core+BIOS begins at C0/H1/S1, while the CP/M filesystem begins at
C2/H0 (DPB OFF=4). 2HD uses 4-KiB allocation blocks and supports
243 blocks total (DSM=242). This image is intended for the
2HD FDD0, with `[DIPSW] 2HD_FDD = true` in the emulator configuration.

The generated 2HD CP/M-86 system has been booted successfully from
physical 2HD FDD0 with current drive E:.

See [the 2HD disk layout](docs/boot-2hd.md) for details.

## Unified FORMAT.CMD (floppy and whole HDD)

`command/FORMAT.A86` unifies the previously tested floppy `FDFORMAT`
behavior and the single MDC HDD as `I:` or `HDD`.

```text
FORMAT B:
FORMAT F: /S
FORMAT HDD
FORMAT I: /S
```

For floppies, the original `/S` and `/L` modes remain. For the HDD,
`/S` creates a bootable whole-disk CP/M-86 image (HDD IPL at LBA0-1,
resident at LBA2-63); without `/S`, it initializes the reserved
cylinder and 16-KiB directory. `FORMAT HDD /L` is refused because the
MDC does not offer physical track formatting.

```sh
make format-inc
make test
```

Transfer `FORMAT.A86`, `FDIPL2D.INC`, `FDIPL2HD.INC`,
and `HDIPL.INC` to CP/M-86 and run `ASM86 FORMAT.A86` followed by
`GENCMD FORMAT`. The original `FDFORMAT.A86` remains for reference.
See [command/README.md](command/README.md) for details and cautions.
The new FORMAT source has static CI coverage; guest ASM86 compilation
and on-emulator use must still be checked on disposable media.

## Whole-HDD CP/M-86 boot (I:, experimental)

CBIOS now has a ninth DPH for the single physical FM-11 MDC hard
disk. I: addresses the **whole raw HDD**, not a partition. Controller
SENSE dynamically selects 16-KiB-block DPB values for all nine
supported M223x/M224x geometries; LBA reads and writes use DMA2.

The companion `hdd_bootrom.bin` loads the two-sector `ipl_hdd.bin`,
which loads the 0x3E00-byte CP/M-86 resident with cold-start drive I:.
HDD cylinder 0 is reserved for IPL and system sectors, and CP/M
directory/data begin in cylinder 1.

```bash
make test
make boot-hdd HDD_MODEL=m2233b
# Optional: HDD_MODEL=m2243b (largest 64.20 MiB model)
```

See [HDD boot implementation and layout](docs/boot-hdd.md).
The CBIOS and boot image are assembled/tested in CI, but actual
8088 emulator boot and I: data I/O still need runtime verification.
The unified FORMAT /S HDD support remains separate work.

## FM-11 CP/M-86 floppy initialization command (experimental)

The `command/FDFORMAT.A86` source handles A:..D: (2D units 0..3)
and E:..H: (2HD units 0..3) by programming the FM-11 FDC and the
8237 DMA directly. Run `make fdformat-inc` to generate the two IPL
include files, then assemble `FDFORMAT.A86` using ASM86 and GENCMD
inside CP/M-86.

The formatter now issues real **WRITE TRACK (F0h)** commands to
both FM-11 FDCs using 6,400-byte 2D and 10,900-byte 2HD track
images. `/S` installs a matching IPL and resident image; `/L`
performs only physical formatting. ASM86 and runtime validation of
this revised command are still pending, so test only on disposable
images first. See
[command/README.md](command/README.md) for build instructions,
disk layout, and safety restrictions.

## References

- [sueyasu/pc98_cpm86](https://github.com/sueyasu/pc98_cpm86):
  CP/M-86 resident layout, CBIOS entry ordering and external CCP/BDOS core.
  PC-98 ROM BIOS calls, memory switches and GVRAM cache are NOT portable.
- [sueyasu/fm11-cpm80](https://github.com/sueyasu/fm11-cpm80):
  FM-11 2D/2HD floppy geometry and physical controller definitions.
  Its Z80/6809 mailbox is not an 8088/6809 ABI.
- [sueyasu/fm11-emulator](https://github.com/sueyasu/fm11-emulator):
  8088/V20 card, 8259 PIC, 8237 DMA and 4 KiB boot ROM model.

## First milestone

The first commit provides:

- A 0x1900-byte CP/M-86 CBIOS scaffold assembled at offset 2500h.
- The 21-entry CBIOS jump table and dynamically initialized memory region table.
- Serial console calls via the FM-11 shared 8251 registers at FD06h/FD07h.
- A standalone 4 KiB **diagnostic** 8088/V20 boot ROM. The reset vector
  transfers to FF00:0000, prints one line to the serial interface and halts.
- Build and layout checks. No generated or proprietary binaries are committed.

The original `bootrom.bin` remains a serial-only diagnostic. The separate
CBIOS integration diagnostic has passed READ/WRITE/RMW tests in the emulator.

## Build

On Linux, install `nasm`, Python 3 and make:

```sh
make
```

Outputs:

- `build/cbios.bin` — 6400-byte CBIOS scaffold.
- `build/bootrom.bin` — 4096-byte 8088/V20 diagnostic ROM.

`make test` checks vector targets, sizes and the reset-vector location.
The CP/M-86 CCP/BDOS core must be supplied separately at
`external/system/cpm86_core.bin` (exactly 0x2500 bytes), as in the
PC-98 port. It is not needed for this initial hardware diagnostic.

## Emulator test

Select the FM-11 EX 8088 card in `/etc/fm11emu.conf`:

```ini
[main]
active = 8088
[main_6809]
installed = true
cpu = 6809
clock_hz = 2000000
[main_8088]
installed = true
cpu = 8088
clock_hz = 8000000
[optional_cpu]
type = none
[display_cpu]
cpu = 6809
clock_hz = 2000000
```

The 6809 card and 8088 card can remain installed together. Use the emulator's
`--8088-rom build/bootrom.bin` setting to run the diagnostic ROM; a PTY
provides the serial interface when supported by the SDL frontend.
Alternatively, test the ROM independently using
`fm11-8088-romtrace --rom build/bootrom.bin --instructions 10000`.
The expected result is a HLT, not an OS boot.

## Read-only 2D FDC diagnostic

A separate firmware image tests one physical Mini-FDC sector without
loading CP/M-86 or modifying the disk:

```sh
make diag
make test
```

This produces `build/fdc2d_diag.bin` (4096 bytes). Configure the emulator
for the 8088 card, mount a **2D** floppy image on the Mini FDC's **unit 0**,
and start `fm11-sdl` with:

```sh
fm11-sdl --8088-rom build/fdc2d_diag.bin
```

The diagnostic ROM waits for one received serial byte before printing anything.
After launching fm11-sdl, note the `Serial PTY: /dev/pts/N` path printed
in its terminal. Open a second terminal, connect with
`screen /dev/pts/N` (or `picocom`), then press any key to start
the diagnostic. This prevents startup output from being missed.
The ROM reads physical cylinder 0, head 0, sector 1 (256 bytes) through
8237 DMA channel 0 into physical RAM 0000:2000. It checks FDC completion
and DMA terminal count, then prints the first 16 bytes in hexadecimal.
Expected output begins with:

```text
FM-11 2D DMA read C0/H0/S1
PASS: TC=1, data: ...
```

On failure it prints `FAIL: FDC status or DMA terminal count`.
**No WRITE SECTOR command is issued**, so the diagnostic does not alter
the floppy. This is a hardware-path test, not a full execution test of
CBIOS `READ`/`WRITE` or of the 128-byte record mapping. The
`fm11-8088-romtrace` standalone tool does not mount a disk, so it is
not sufficient for a successful floppy-read test. `make test` performs
static ROM checks only; a successful test is not a claim of emulated or
physical I/O success.

## CBIOS READ/WRITE integration diagnostic

Build a **dedicated disposable 2D test image** and 8088 diagnostic ROM:

```sh
make cbios-diag
make test
```

Outputs: `build/cbios_diag.bin` (4096-byte ROM) and
`build/cbios_diag_2d.img` (327680-byte raw 2D floppy). Never use
a disk containing valuable data for this test. The generated image
contains the actual `build/cbios.bin` at C0/H0/S2 onward, followed
by a scratch sector at C1/H0/S1. The diagnostic ROM loads all 25
physical sectors (0x1900 bytes) of the real CBIOS to RAM
0000:2500, then calls its existing 21-entry vector table.
It does **not** enter the unfinished INIT/WBOOT or require the
external CP/M-86 CCP/BDOS core.

With the 8088 selected as the main CPU in `/etc/fm11emu.conf`,
start the SDL frontend using your normal 6809 main-board ROM (required
for SDL floppy mounting) and the dedicated raw image:

```sh
fm11-sdl --main-rom /path/to/boot6809.bin \\
  --8088-rom build/cbios_diag.bin \\
  --floppy2d build/cbios_diag_2d.img --floppy-drive 0
```

The ROM waits for one incoming serial byte before it starts: attach
`screen /dev/pts/N` to the `Serial PTY:` announced by fm11-sdl,
and press any key.

Expected serial output:

```text
CBIOS 128-byte record test
CBIOS loaded from 2D disk
PASS: records 0 and 1 read
PASS: WRITE, RMW, verify, restore
```

The diagnostic now prints `STEP:` markers around the first CBIOS
calls, including `SELDSK` and the two logical `READ` operations.
If `fm11-sdl` reports an invalid opcode, capture the last printed
`STEP:` marker. The cross-segment call gate resides at 0000:7100
and uses only 8086 PUSH/RET instructions, avoiding the previous
FF-group indirect CALL. An emulator exception alone does not prove a
CBIOS disk failure; the step markers distinguish dispatch failure from
the actual FDC/record transfer.

The ROM selects drive A:, track 2 (physical C1/H0), and reads logical
records 0 and 1 into distinct RAM buffers. It checks both expected
byte patterns. It then writes a third pattern into record 0, reads
it back, confirms that record 1 was preserved, and restores the
original record 0. A failed write or restore can still leave the
disposable scratch sector modified. This is a functional test of
CBIOS `READ`/`WRITE`, not just direct FDC register access. The
serial output, not the static `make test` result, establishes whether
the emulated FDC, DMA, and CBIOS work together.

## Experimental CP/M-86 2D cold boot

The new `src/iplrom.asm` reads **62 contiguous physical sectors**
(256 bytes each) from Mini-FDC drive 0, starting at C0/H0/S1. It
loads the 0x3E00-byte resident image into segment `0400h`, checks
the CBIOS jump-vector opcode at `0400:2500`, and transfers to CBIOS
`INIT`. The resident consists of a separately supplied CP/M-86
CCP/BDOS core (0x2500 bytes) followed by `build/cbios.bin` (0x1900
bytes). Neither the proprietary core nor its binaries are committed.

Provide the external core at `external/system/cpm86_core.bin`
(or set `CPM86_CORE` in the make invocation).

To include any CP/M-compatible files on the boot disk, put the
files in `external/commands/`. Both 2D and 2HD builders accept
`.CMD`, `.A86`, `.INC`, `.TXT` and other 8.3 names. Files are
stored byte-for-byte under uppercase CP/M names. For example:

```text
external/commands/
  PIP.CMD
  STAT.CMD
  ED.CMD
  FDFORMAT.A86
  FDIPL2D.INC
  FDIPL2HD.INC
```

The image uses the CBIOS 2D DPB: 2 KiB allocation blocks,
16 one-byte block numbers per directory entry (DSM=151), EXM=1,
and 64 directory entries. A file larger than 32 KiB is split
across multiple directory entries. Duplicate 8.3 names, invalid
names, full directory, or insufficient free data blocks cause an
explicit build error. `make boot` picks up files present when
Make runs; changes to existing files trigger image regeneration.
When adding/removing files, rerun `make boot`; if removing a file
without changing any other dependencies, `make -B boot` guarantees
rebuilding the disk.

```sh
make test            # checks assembly/geometry, needs no external core
make boot            # requires a real 0x2500-byte core
```

`make boot` generates `build/iplrom.bin` (4 KiB reset ROM) and
`build/fm11_cpm86_2d.img` (320 KiB, raw 2D). If the core is not
available, the ROM alone can be assembled with `make build/iplrom.bin`.
The first **four** logical side-tracks (two cylinders, 16 KiB) are
reserved for the resident image; the CP/M directory starts
at physical cylinder 2. Corresponding DPB parameters are `OFF=4`,
`DSM=151`. The last 512 bytes of the system area are left erased.

Start the SDL frontend with the 8088 main CPU selected, an installed
6809 card for the current floppy-mounting frontend, and:

```sh
fm11-sdl --main-rom /path/to/boot6809.bin \\
  --8088-rom build/iplrom.bin \\
  --floppy2d build/fm11_cpm86_2d.img --floppy-drive 0
```

As with the diagnostics, connect to the announced `Serial PTY:`
with `screen /dev/pts/N` and press any key to start the ROM.
A successful *loader* should emit:

```text
FM-11 CP/M-86 2D IPL: loading resident
FM-11 CP/M-86 IPL: CBIOS vector OK, entering INIT
FM-11 CP/M-86 BIOS: serial initialized
```

The IPL, CBIOS INIT, CCP prompt and empty-directory `DIR` have been
confirmed in the FM-11 emulator. The new command-populated image still
requires live verification with `DIR`, `STAT`, `PIP` and executable
`.CMD` files. `WBOOT`, runtime verification of dynamic RAM sizing, and
more complex file operations also require testing. Avoid using valuable media: this is
experimental firmware, and the CBIOS supports write operations.

## Installed RAM and dynamic TPA

CBIOS `INIT` probes installed RAM in **8 KiB steps** (128 KiB to 1 MiB)
on the current FM-11 emulator, and `GETSEGT` returns a dynamically
sized MRT. Intermediate sizes such as 192 KiB are detected as well.  The
single TPA region begins at segment `0800h` (physical `08000h`)
and extends to installed RAM's end, except that the 8088 boot ROM
at physical `FF000h-FFFFFh` is excluded at 1 MiB.

| Installed RAM | TPA size | MRT length (paragraphs) |
| --- | --- | --- |
| 128 KiB | 96 KiB | 1800h |
| 256 KiB | 224 KiB | 3800h |
| 384 KiB | 352 KiB | 5800h |
| 512 KiB | 480 KiB | 7800h |
| 640 KiB | 608 KiB | 9800h |
| 768 KiB | 736 KiB | B800h |
| 896 KiB | 864 KiB | D800h |
| 1024 KiB | 988 KiB | F700h |

The probe modifies no RAM permanently: both the CBIOS anchor and each
candidate byte are restored after testing.  It assumes the emulator's
RAM aliasing model; original hardware memory-decode behavior still
needs verification.  `make test` checks the complete size/region table
at all 113 capacities in 8 KiB increments through a model/static
regression; **guest runtime testing remains
necessary**.  The optional CBIOS self-test also prints the computed
MRT length as `MRT TPA paragraphs=5800` (example for 384 KiB).

See [docs/architecture.md](docs/architecture.md) for the probe
algorithm and hardware compatibility notes.

## Next milestones

1. Verify command-populated 2D media using DIR and external CMD execution.
2. Fix any remaining WBOOT/memory-region and CCP/BDOS ABI issues.
3. Validate CP/M file creation/read/write on disposable 2D media.
4. Validate all eight FDD units and native 2HD boot on the emulator.
5. Test warm boot, standard CP/M commands, and real FM-11 hardware.

See `docs/architecture.md` for hardware boundaries and open questions.
