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

The first disk-BIOS step now provides DPH/DPB records for A:..D: as four
independent 2D units. The provisional filesystem parameters are:

- 32 CP/M records (128 bytes each) per logical side-track.
- 2 KiB allocation blocks; 156 data blocks numbered 0..155.
- 64 directory entries (one reserved allocation block).
- Two reserved side-tracks at the start of the disk.
- Per-drive CSV (16 bytes) and ALV (20 bytes), plus a shared 128-byte DIRBUF.

These parameters describe a proposed CP/M-86 filesystem layout, **not** the
FM-11 boot-track format. They require verification when an IPL and disk-image
builder exist. The driver returns errors on READ/WRITE until the direct
8088 FDC/8237 transport and 256-to-128-byte deblocking are implemented.
The DPH pointers must not be treated as evidence that media I/O works.

The initial 2D physical-sector transport is now present in `src/cbios.asm`
as `fdc2d_read` and `fdc2d_write`.  Both use the Mini FDC registers
FD18h/FD19h/FD1Ah/FD1Ch/FD1Dh and 8237 channel 0 (10h/11h/18h/1Ah/
1Bh/1Ch/20h).  The transfer is exactly 256 bytes into or out of the
BIOS-local `fdc2d_buffer`.  Entry registers are AL=drive, CH=cylinder,
DH=head, CL=physical-sector (1-based); CF reports success/failure.
The implementation checks DMA terminal count and FDC completion status,
and masks CH0 on return. DMA CH0 is owned exclusively during the call.

**Logical I/O:** CP/M-86 `READ` and `WRITE` now use 128-byte
records, numbering 0..31 on each logical side-track (0..79).  The
logical-to-physical mapping is cylinder = track / 2, head = track % 2,
sector = record / 2 + 1, half-sector = record % 2.  A read transfers
the selected half of `fdc2d_buffer` to the caller's DMA segment:offset.
A write always reads the full 256-byte sector first, replaces the
selected half with the caller's 128-byte record, and writes the full
sector back.  This preserves the other 128-byte record without a
dirty-sector cache or deferred flush.  Both operations return AL=0 on
success and AL=1 on error.

**Limitations:** Only Mini-FDC drive 0 is supported by the current
emulator; attempts to perform CP/M disk I/O on drives B:..D: are
rejected, despite the provisional DPH entries.  Each record write
performs a physical read and write.  No retry, media-change detection,
or real-hardware timing validation is implemented.  The bounce buffer
is checked against the 8237 64 KiB page boundary, and the caller DMA
offset is checked for 128-byte segment wrapping.  An IPL must
establish the final resident segment and validate memory ownership.

Next implement 2D disk boot loading and end-to-end emulator tests,
then extend the controller for additional drive units and 2HD media.

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
