# FM-11 CP/M-86 2D disk IPL / D88 image

`make boot-d88` produces a disk image for testing with an FM-11
emulator using a floppy-loading 8088 boot ROM, rather than the temporary
4-KiB serial IPL ROM from `src/iplrom.asm`.

Requirements are identical to `make boot`: NASM, Python 3, the
0x2500-byte `external/system/cpm86_core.bin`, and the desired
`external/commands/*.CMD` binaries.

```sh
git pull
make boot-d88
```

Outputs:

- `build/ipl_2d.bin` — 512-byte 8088 floppy IPL
- `build/fm11_cpm86_boot_2d.raw` — 327680-byte IPL-equipped raw 2D disk
- `build/fm11_cpm86_boot_2d.d88` — D88 disk with standard CHRN headers

No changes are made to `build/fm11_cpm86_2d.img`, which retains the
original ROM IPL-compatible layout.

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
CBIOS is still assembled at ORG 2500h, and its DPB OFF=4 and all file
allocation values are unchanged.

## Important boot-ROM assumption

**The disk IPL is written under the explicit assumption that the
original FM-11 8088 boot ROM loads C0/H0/S1-S2 (512 bytes) into
physical 0000:0400 and jumps to 0000:0400.** This is not verified
against the specific original emulator/8088 ROM in use. The known FM-11
6809 2D boot ROM follows the 512-byte-at-0400 convention, but it does
not establish identical behavior for 8088 boot ROMs. If the original
8088 ROM uses a different bootstrap entry location, first-stage load
length, or disk-header convention, the IPL must be adapted.

The disk IPL uses the same 8237 DMA and Mini-FDC I/O ports already
used by the working experimental 8088 ROM loader, but its successful
execution on the original emulator has **not** been demonstrated.
Using the D88 alone cannot guarantee correct boot if the original
emulator or ROM uses different FDC/DMA behavior.

The build target verifies D88 geometry, sector payload round-trips,
exact resident positioning and preservation of the CP/M filesystem.
These structural tests do not constitute a runtime boot test.
