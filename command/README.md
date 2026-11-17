## Unified FORMAT (floppy 2D/2HD and whole MDC HDD)

The new `FORMAT.A86` supersedes `FDFORMAT.A86` as the supported
entry point. The older floppy-only source remains available for
reference. Both `HDD` and `I:` select the one physical MDC HDD.

| Command | Effect |
|---|---|
| `FORMAT B:` | Physical WRITE TRACK of 2D FDD B: |
| `FORMAT F: /S` | Physically format 2HD and install boot IPL/resident |
| `FORMAT B: /L` | Physical track format only (FDD) |
| `FORMAT HDD` | Whole-HDD logical format (IPL area + directory) |
| `FORMAT I:` | Same as `FORMAT HDD` |
| `FORMAT HDD /S` | Whole-HDD logical format, IPL and CP/M-86 resident |
| `FORMAT I: /S` | Same bootable HDD format |

MDC HDD offers sector READ/WRITE, **not a physical WRITE TRACK
operation**. `FORMAT HDD /L` and `FORMAT I: /L` are explicitly
rejected **before any modification to the HDD**.

The HDD uses the same binary-LBA mode and DMA channel 2 as the CBIOS
`I:` implementation. All nine supported model geometries are
detected via MDC SENSE. The normal HDD format writes E5h to all sectors
of physical cylinder 0 and the first 64 sectors of cylinder 1 (the
16 KiB CP/M directory allocation block). File data blocks beyond the
directory are not physically overwritten, but CP/M no longer references
them after the directory is initialized.

For `/S`, FORMAT reads the 0x3E00-byte source resident from the
currently selected A:, E: or I: system drive **before** overwriting
the destination. It checks and patches the CBIOS INIT boot-drive
immediate to A: (0), E: (4), or I: (8). For the HDD target, it installs
the exact 512-byte IPL in physical LBA0-1 and the resident in LBA2-63,
then reads back and compares all 64 sectors.

**Do not execute FORMAT against an important HDD image.** It does
not repartition or resize a host image: the emulator must already have
a supported raw MDC image mounted. Use disposable images while testing.

### Build FORMAT.CMD under CP/M-86

On Linux, prepare all three ASM86 INCLUDE files:

```sh
make format-inc
make test
```

Copy these files into the same directory on a CP/M-86 disk:
`command/FORMAT.A86`, `command/FDIPL2D.INC`,
`command/FDIPL2HD.INC`, and `command/HDIPL.INC`.

```text
I>ASM86 FORMAT.A86
I>GENCMD FORMAT
I>FORMAT HDD /S
```

The `I>` prompt is illustrative; the command may be assembled on
any CP/M-86 boot drive. An **ASM86 1.1 assembly and emulator execution
test of the unified FORMAT** have not yet been performed in CI.
The Linux tests verify its static source structure and the IPL
templates; a disposable HDD image is required for runtime testing.

---

# FM-11 CP/M-86 FDFORMAT

This is an FM-11 hardware port of the command interface from
[`pc98_cpm86/command/FDFORMAT.A86`](https://github.com/sueyasu/pc98_cpm86/blob/main/command/FDFORMAT.A86).
It is a new direct-FDC implementation, not a rename or minor edit of the
PC-9801 ROM BIOS `INT 1Bh` implementation.

## Physical formatting modes

The FM-11 FDFORMAT now issues the genuine WD17xx **WRITE TRACK (F0h)**
command on every physical side-track. It constructs address marks,
sector CHRN fields, data marks, CRC generation tokens, E5h data, and
4Eh gaps, as in the FM-11 NitrOS-9 formatter. This requires the
emulator WRITE TRACK implementation.

- `FDFORMAT B:`: physically format a 2D data disk, including cylinder 0
  and an empty CP/M directory (all E5h)
- `FDFORMAT F:`: physically format a 2HD data disk
- `FDFORMAT /S B:`: format a bootable 2D disk and install IPL/resident
- `FDFORMAT /S F:`: format a bootable 2HD disk and install IPL/resident
- `FDFORMAT /L B:`: physically format only; do not install system files

All commands require explicit confirmation and **destroy the entire
target disk**. The source system resident (0x3E00 bytes) is read
and checked from the **current A: or E: drive** before the target
is overwritten. Unlike the earlier implementation, a running E:
(2HD) system may make a 2D boot disk, and a running A: (2D) system
may make a 2HD boot disk. The /S path validates the existing CBIOS
INIT code and adjusts its cold-boot drive to A: or E: in the saved
image. Unknown CBIOS layouts are rejected before formatting. The
resident comes from disk, never from the live in-memory CCP/BDOS.

The current implementation intentionally accepts only the native
40x2x16x256 (2D) and 77x2x26x256 (2HD, with C0/H0 128-byte FM)
geometries. The emulator must have a mounted D88 or raw image with
the correct drive configuration. WRITE TRACK is not a mechanism for
creating a new host image from nothing.

Because the 8237 cannot cross a 64-KiB physical DMA page in one
transfer, FDFORMAT reserves two 10,900-byte alternatives and chooses
a DMA-safe track buffer. Transfer length is 6,400 bytes for 2D DMA0
and 10,900 bytes for 2HD DMA1. Only the 2HD boot side-track uses
128-byte sectors; all other track data uses 256-byte sectors.

### Drive mapping

| CP/M | Controller | Physical unit | Standard physical format |
|---|---|---|---|
| A:..D: | Mini-FDC, 8237 channel 0 | 0..3 | 40 x 2 x 16 x 256 bytes |
| E:..H: | Standard FDC, 8237 channel 1 | 0..3 | 77 x 2 x 26 x 256 bytes; C0/H0 uses 128-byte FM |

The 2HD special boot track is physically created as 128-byte FM sectors.
The resident image begins at C0/H1/S1. On 2D, the boot IPL occupies
C0/H0/S1-S2, and the resident begins at C0/H0/S3.

## Generate includes on Linux

```sh
make fdformat-inc
make test
```

Generated files:

- `command/FDIPL2D.INC` from `build/ipl_2d.bin`
- `command/FDIPL2HD.INC` from `build/ipl_2hd.bin`

The included `command/bin2a86.py` is ported from the PC-98 project
and emits CRLF lines, `0XXh` hexadecimal byte syntax, and CP/M text
EOF 1Ah. The Makefile checks the generated byte values exactly.

## Build the command within CP/M-86

Copy `command/FDFORMAT.A86`, `command/FDIPL2D.INC`,
and `command/FDIPL2HD.INC` into the same CP/M-86 directory.

```text
ASM86 FDFORMAT.A86
GENCMD FDFORMAT
```

The expected output is `FDFORMAT.CMD`. Place it in
`external/commands/` before running `make boot-d88` or
`make boot-2hd` to include it in new system images.

**Runtime validation on the 8088/V20 emulator and an ASM86/GENCMD
round-trip has not yet been performed**; the CI checks only verify the
IPL bytes and existing NASM/Python build targets. Use disposable media
for the first tests. Do not use irreplaceable floppy images.

## Validation

The Linux CI tests the generated IPL includes, image layout, and
FDFORMAT static labels/parameters. The emulator WRITE TRACK path
was validated separately with C++ unit tests and NitrOS-9 `format`.
**The FDFORMAT.A86 source still needs to be assembled with the actual
ASM86/GENCMD toolchain and run on disposable 2D/2HD images.**

## Include arbitrary files in boot images

Place any CP/M **8.3-named regular files** such as `.A86`, `.INC`,
`.TXT`, `.DAT`, or `.CMD` in `external/commands/`.
Both `make boot-d88` and `make boot-2hd` automatically include
these files. `README.md` is excluded as host documentation.
Filenames must meet CP/M 8.3 naming rules; duplicate names after
case folding, full disks and full directories cause a build error.
