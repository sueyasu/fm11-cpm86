# FM-11 CP/M-86 2D disk IPL / D88 image

`make boot-2d` produces a disk image for testing with an FM-11
emulator using the original FM-11 floppy-loading 8088 boot ROM.

Requirements: NASM, Python 3, the
0x2500-byte `external/system/cpm86_core.bin`, and the desired
`external/commands/*.CMD` binaries.

```sh
git pull
make boot-2d
```

Outputs:

- `build/ipl_2d.bin` — 512-byte 8088 floppy IPL
- `build/fm11_cpm86_2d.raw` — 327680-byte IPL-equipped raw 2D disk
- `build/fm11_cpm86_2d.d88` — D88 disk with standard CHRN headers

The intermediate `build/fm11_cpm86_2d_stage.img` is a build-only filesystem staging image, not a bootable disk.

## Layout

The disk is 40 cylinders, 2 heads, 16 sectors per head, 256 bytes per
sector. D88 media type is 0 (2D). D88 track entries follow cylinder/head
order and sector IDs are 1..16, N=1.

| Raw disk offsets | Contents |
|---|---|
| 0000h..01FFh | 512-byte 8088 disk IPL, C0/H0/S1-S2 |
| 0200h..26FFh | 0x2500-byte CCP/BDOS, starts C0/H0/S3 |
| 2700h..3FFFh | 0x1900-byte CBIOS, after CCP/BDOS |
| 4000h..end | Original CP/M directory and commands, unchanged |

The disk IPL loads 62 sectors from C0/H0/S3 onward into physical RAM
04000h..07DFFh and jumps to 0400:2500, the resident CBIOS INIT vector.
The disk IPL issues RESTORE with DMA masked and SEEK at cylinder transitions.
CBIOS is still assembled at ORG 2500h, and its DPB OFF=4 and all file
allocation values are unchanged.

## Original emulator 8088 ROM compatibility (v128; development history)

Inspection of the uploaded original emulator source (`Fm11/BootRom86.h`,
v128) shows its floppy boot code performs a far jump to **`07C0:0000`**
(physical `07C00h`) after loading the floppy bootstrap, not to the
`0000:0400` address used by the 6809 ROM. In the previous version this
entry-point mismatch prevented correct startup.

The revised disk IPL starts at offset zero in the loaded segment, copies
its full 512 bytes to `0100:0000` (physical `01000h`), and jumps there
**before** reading the following 62 physical sectors into
`0400:0000`...`0400:3DFF`. Without relocation, the last two resident
sectors would overwrite the running IPL at physical `07C00h`.

The image still uses the same 8237 DMA / Mini-FDC interfaces as the
CBIOS, and its disk geometry matches the original
emulator's D88 parser (`MainCpu.cpp`, `MainCpu.h`). It has not yet been
executed on the uploaded original emulator, so this is a source-level
compatibility fix rather than a confirmed successful boot.

The build target checks D88 geometry, sector payload round-trips, exact
resident placement and preservation of the CP/M filesystem. These
structural checks do not constitute a runtime boot test.

## USART initialization and silent boot

The 2D and 2HD disk IPLs no longer emit serial progress or error markers.
They still initialize the shared 8251 via FD07h if TXRDY is clear, using
three zero control writes followed by 40h, 4Eh and 37h (TX/RX enabled,
DTR asserted). An already-ready USART is left untouched, avoiding the
original emulator's DTR-triggered terminal disconnect. The IPL does not
wait for terminal input. The CBIOS retains its ordinary startup banner
and console routing.

The existing FDC/DMA checks and CBIOS first-vector E9h check remain in
place; a failure halts without printing a diagnostic character.

Earlier development builds emitted I/R/dots/J and E/V failure markers.
Those routines have been removed from both normal floppy IPLs. The HDD
IPL did not contain these markers. Standalone diagnostic ROMs and the
CBIOS self-test remain available separately.

Rebuild floppy images with `make boot-2d` and `make boot-2hd`.
To update IPL templates embedded in FORMAT.CMD, run `make format-inc`
and rebuild the command as described in [command/README.md](../command/README.md).
