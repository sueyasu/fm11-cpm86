# FM-11 CP/M-86 v1.1 port

This project is an initial port of CP/M-86 to the Fujitsu FM-11's 8088
main CPU card (or NEC V20 replacement). It is **not yet bootable**.

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
- The 21-entry CBIOS jump table and provisional memory region table.
- Serial console calls via the FM-11 shared 8251 registers at FD06h/FD07h.
- A standalone 4 KiB **diagnostic** 8088/V20 boot ROM. The reset vector
  transfers to FF00:0000, prints one line to the serial interface and halts.
- Build and layout checks. No generated or proprietary binaries are committed.

Disk BIOS entries currently return errors or no installed drives; they must
not be used to access a real disk. The diagnostic ROM does not load CP/M-86.

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

## Next milestones

1. Confirm 8088 ROM reset and serial console on `fm11-sdl`/romtrace.
2. Implement FM-11 floppy IPL and direct 8088 8237/FD18 or FD30 disk transfer
   with correct controller and DMA bank/sector semantics.
3. Complete CBIOS SELDSK, READ/WRITE, 128-byte deblocking and drive tables.
4. Combine the externally supplied CP/M-86 CCP/BDOS core and CBIOS into a
   bootable 2D/2HD D88 image using a format-specific image builder.
5. Verify cold/warm boot, console, file I/O and standard CP/M-86 commands.

See `docs/architecture.md` for hardware boundaries and open questions.
