# FM-11 CP/M-86 whole-HDD boot (I:)

The FM-11 emulator's MDC adapter presents **one 256-byte-sector HDD**.
This implementation does not use a SCSI ID or a partition table. CP/M
logical drive `I:` maps to the entire HDD. The maximum supported
model, M2243B, has 747 cylinders, 11 heads and 32 sectors/track
(67,313,664 bytes, ~64.20 MiB).

## On-disk layout

The default bootable raw HDD image has:

| Physical position | Contents |
|---|---|
| LBA 0–1 | 512-byte 8088 HDD IPL |
| LBA 2–63 | 62 x 256-byte CP/M-86 resident (CCP/BDOS+CBIOS) |
| Remainder of cylinder 0 | Reserved (E5h) |
| Cylinder 1 onward | CP/M-86 I: filesystem |
| First 16 KiB of filesystem | 512-entry CP/M directory (E5h empty) |

The standard Fujitsu 8088 boot ROM reads the first two HDD sectors
(LBA 0–1) into 07C0:0000 and transfers control to the 512-byte on-disk
IPL. The IPL relocates to 0100:0000, switches MDC into binary-LBA mode,
loads the 0x3E00-byte resident at 0400:0000 and enters CBIOS INIT.
The disk IPL uses the MDC command 11h (parameter 70h) and DMA channel 2.
The custom 4-KiB HDD reset ROM has been removed; the shared
`src/hdd_boot_io.inc` is still required by `src/ipl_hdd.asm`.

The standard-ROM handoff was established during FM-11 CP/M-80 work.
Actual standard-ROM boot of this CP/M-86 image is not yet verified.

## Drive parameters

The new DPH is assigned to I: (drive number 8). The CBIOS uses MDC
SENSE (command 14h) to determine geometry, and sets the I: DPB at
first SELDSK. SPT=64 128-byte records per physical head-track,
BSH=7, BLM=127, EXM=7, DRM=511, AL0=80h, CKS=0,
OFF=number of physical heads, and DSM=((cylinders-1)*heads)/2-1.

16 KiB allocation blocks use 16-bit block numbers, including on
the largest supported model. No subpartitioning is required.

## Building

Provide the separately licensed CP/M-86 core at
`external/system/cpm86_core.bin` (exactly 0x2500 bytes).

```bash
make test
make boot-hdd HDD_MODEL=m2233b
# or: make boot-hdd HDD_MODEL=m2243b
```

Outputs:

- `build/ipl_hdd.bin` – 512-byte on-disk HDD IPL
- `build/cbios_hdd.bin` – 0x1900-byte CBIOS booting on I:
- `build/fm11_cpm86_boot_hdd.img` – whole-HDD raw image

In the FM-11 emulator use the **8088 main CPU** configuration.
In its `fm11emu.conf` (or a dedicated `--config` file), assign the
single raw HDD image:

```ini
[hdd]
image = /absolute/path/to/fm11_cpm86_boot_hdd.img
```

Keep the original Fujitsu 8088 ROM configured, including the existing
display/ANK ROMs. Enable HDD boot selection in the emulator DIP-switch
configuration. Do not override `--8088-rom` with a custom HDD ROM:

```sh
fm11-sdl --config /path/to/fm11emu.conf
```

The standard boot ROM, not the CP/M-86 CBIOS console option, controls
any input wait before the disk IPL starts.
The IPL boots CP/M-86 with initial drive `I:` (drive number 8).
Do not mount this HDD image concurrently elsewhere.

`make hddipl-inc` creates `command/HDIPL.INC` from the identical IPL
binary used by the unified FORMAT /S command. See [command instructions](../command/README.md).

**Validation status:** NASM and image-structure checks run in GitHub
Actions, including the I: INIT boot-drive value, the 512-byte disk IPL,
and resident layout. These structural checks do not prove execution of
the original ROM boot path. Real hardware validation and testing every supported geometry remain necessary. Use disposable images for destructive tests.

## Supported models

| Model | Cylinders | Heads |
|---|---:|---:|
| m2230b | 315 | 2 |
| m2231b | 157 | 4 |
| m2232b | 157 | 6 |
| m2233b | 315 | 4 |
| m2234b | 315 | 6 |
| m2235b | 315 | 8 |
| m2241b | 747 | 4 |
| m2242b | 747 | 7 |
| m2243b | 747 | 11 |

Each has 32 256-byte sectors per physical track.
