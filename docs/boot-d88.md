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

## Original emulator 8088 ROM compatibility (v128)

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
experimental 8088 loader, and its disk geometry matches the original
emulator's D88 parser (`MainCpu.cpp`, `MainCpu.h`). It has not yet been
executed on the uploaded original emulator, so this is a source-level
compatibility fix rather than a confirmed successful boot.

The build target checks D88 geometry, sector payload round-trips, exact
resident placement and preservation of the CP/M filesystem. These
structural checks do not constitute a runtime boot test.

## Serial diagnostics in the disk IPL

The 512-byte IPL initializes the shared 8251 on ports FD07h (status)
and FD06h (data), then prints single-character stage markers:

- `I` — entered the disk IPL at `07C0:0000` and initialized serial.
- `R` — copied the IPL to `0100:0000` and entered the relocated code.
- `.` — one 256-byte resident sector read succeeded; 62 dots expected.
- `J` — confirmed the CBIOS E9h vector and about to jump to INIT.
- `E` — sector-read failure (FDC status or DMA terminal-count check).
  The compact 512-byte IPL omits hexadecimal CHS reporting to fit the boot sectors.
- `V` — loaded CBIOS first vector byte is not E9h.

The `E` / `V` cases halt without further output. `J` proceeds to the
CBIOS, so a later CBIOS banner should appear. To avoid consuming the
first serial character, the IPL does **not** wait for terminal input.

**Connect the serial terminal before starting the original emulator.**
An early `I` may be lost if the PTY is attached after the IPL begins.
The output is designed to be compact enough for the 512-byte boot sector,
rather than provide a verbose interactive diagnostic.

## 8088 original emulator: serial TX wait at 07CA9h

The original emulator v128 implements the shared 8251 as a state machine
(`Fm11/MainCpu.cpp`, `Fm11RS232C`). A cold or warm boot need not leave
its mode/command parser in the initial `Init=0` state. Previously, the
disk IPL wrote only `4Eh` (mode) and `37h` (command). If interpreted in
the wrong parser state, TXRDY bit 0 can remain clear and the first
diagnostic output spins in `IN AL,DX / TEST AL,1 / JZ`. On the original
emulator a stop at physical `07CA9h` with `JZ FB` matches this loop.

The disk IPL now issues three zero control writes, `40h` (8251 internal
reset), `4Eh` (asynchronous mode) and `37h` (enable TX/RX). These
writes synchronize the 8251 parser from any of its four initial states.
It also bounds the serial TX-ready polling, so a missing USART or
non-ready transmitter cannot block the resident disk loader forever.
Missing stage letters therefore no longer necessarily mean the disk
IPL was never entered: examine the PC or later resident startup as well.
