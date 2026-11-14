# FM-11 8088/V20 CP/M-86 design notes

## CPU and memory

The FM-11 EX main 8088 card can coexist with the 6809 card. The hardware
selection (DIP) chooses which is active. Unlike the Z80 CP/M-80 port, the
first CP/M-86 implementation will use the **8088 card directly** for BIOS
console and disk requests; it does not assume a 6809 I/O-server trampoline.

Current emulator model (`Main8088Bus`): 1 MiB linear CPU-card RAM,
ROM mapped at FF000h-FFFFFh, reset fetch at FFFF0h. The IPL must establish
8088 real-mode CS:IP, DS/ES/SS, the resident memory segment, and the CP/M-86
BIOS entry without relying on PC-9801 INT 1Bh.

## CP/M-86 binary layout (reference port)

The existing `pc98_cpm86` resident image has a 0x2500-byte externally
provided CCP/BDOS core followed by BIOS at offset 2500h, using a 0x1900
byte BIOS area. This project initially reserves the same offsets and
retains the CBIOS 21-entry jump table, pending actual FM-11 boot verification.
The first-stage diagnostic ROM does not enter this resident image.

## FM-11 devices

- Serial data/status: I/O ports FD06h and FD07h. The current emulator's
  shared USART8251 advertises TX-ready at status bit 0 and RX-ready at bit 1.
- Mini FDC: FD18h–FD1Fh (2D media). Standard FDC: FD30h–FD37h (2HD).
- 8088 card: 8237 DMA at ports 10h–23h; 8259 PIC at 00h/01h.
- 2D: 40 cylinders, 2 heads, 16 sectors per side, 256 bytes/sector.
- 2HD: 77 cylinders, 2 heads, 26 sectors per side, 256 bytes/sector.
  The special boot track has different sector sizes; IPL must account for it.
- CP/M physical sectors need 128-byte logical record deblocking.

The first BIOS provides only serial console service and returns disk errors.
Actual FDC/DMA integration, timeouts and retry handling are separate
milestones.

## Known emulator integration questions

- Verify that writes to the 8251 mode and command port are handled as
  expected by the ROM and frontend.
- Validate that the 8088 card can read floppy-controller status and program
  the 8237 using the FM-11 controller's port mapping.
- Confirm how the FM-11 EX ROM normally boots the 8088 card and choose a
  compatible or intentionally custom 2D/2HD boot-sector format.
- Check the CP/M-86 1.1 core's memory-region table and entry conventions
  with an actual resident-image boot before treating its provisional values
  as final.

No PC-98 ROM BIOS, GVRAM caching, FDD geometry, or PC-98 keyboard/CRT code
will be transplanted unchanged.
