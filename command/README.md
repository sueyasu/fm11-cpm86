## Unified FORMAT (floppy 2D/2HD and whole MDC HDD)

`FORMAT.A86` is the sole maintained floppy/HDD formatter source. Both `HDD` and `I:` select the one physical MDC HDD.

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
any CP/M-86 boot drive. `FORMAT.CMD` has been assembled and exercised successfully under CP/M-86
in the FM-11 emulator. Linux CI checks the source structure and IPL
images; continue using disposable media for destructive tests.

