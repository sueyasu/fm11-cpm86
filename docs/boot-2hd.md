# FM-11 CP/M-86 native 2HD bootable D88

The CBIOS uses fixed drive letters independently of the boot medium:

- A:..D: 2D Mini-FDC units 0..3, DMA channel 0.
- E:..H: 2HD standard FDC units 0..3, DMA channel 1.

The 2D IPL starts CP/M-86 on A:, whereas the 2HD IPL starts on E:.

## Build

Provide the external 0x2500-byte CP/M-86 core at
`external/system/cpm86_core.bin`, optionally supply command files in
`external/commands/`, and run `make boot-2hd`.

Outputs are `build/ipl_2hd.bin` (512 bytes),
`build/cbios_2hd.bin` (0x1900 bytes),
`build/fm11_cpm86_2hd.raw` (256-byte slot representation), and
`build/fm11_cpm86_2hd.d88` (native mixed-sector D88).

## Physical layout

| Physical location | Format | Data |
|---|---|---|
| C0/H0/S1..S26 | 26 x 128 bytes, FM | IPL in S1..S4 |
| C0/H1 | 26 x 256 bytes, MFM | Resident sectors 1..26 |
| C1/H0 | 26 x 256 bytes, MFM | Resident sectors 27..52 |
| C1/H1 | 26 x 256 bytes, MFM | Resident sectors 53..62; reserve remainder |
| C2/H0 onward | 26 x 256 bytes, MFM | CP/M filesystem |

The IPL expects the 8088 boot-ROM entry at physical 07C00h and
relocates itself to physical 01000h, then DMA-loads 62 x 256-byte
resident sectors at 04000h..07DFFh, entering CBIOS at 0400:2500.

The 2HD DPB is SPT=52, BSH=5, BLM=31, EXM=3, DSM=242, DRM=63,
AL0=80h, AL1=0, CKS=16, OFF=4. There are 243 usable 4-KiB
allocation blocks, including directory block 0. A 31-byte ALV
and 16-byte CSV are reserved per 2HD drive.

The raw image uses 256-byte sectors throughout for logical tooling
compatibility; the first four IPL sectors occupy the first 128 bytes
of their 256-byte slots. The D88 stores those as actual 128-byte FM
records. The raw and D88 files are therefore not byte-identical.

Run `make test` without a proprietary CP/M core to verify geometry,
D88 record headers, CBIOS layout, resident placement, and allocations
using a synthetic **nonbootable** core. E: boot has been confirmed in the emulator; real hardware validation remains necessary.

Configure the emulator with a 2HD D88 image in physical 2HD FDD0
and `[DIPSW] 2HD_FDD=true`. The booted OS should initially select E:.
