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
The experimental 2D IPL ROM now loads this resident image at segment
0400h and enters CBIOS INIT at 0400:2500. The initial BIOS stack tops
out at 0400:4000 (physical 08000h), below the TPA base at segment 0800h. A usable CCP/BDOS boot is
not yet verified.

## Cold-boot RAM detection and CP/M-86 Memory Region Table

CBIOS `INIT` calls `init_mrt` before entering CCP.  With the FM-11
emulator's configurable RAM address decoder, memory not populated above
the installed capacity aliases RAM at the beginning of the address
space.  The routine tests physical 128 KiB boundaries (128 through
896 KiB) by writing a marker at the *same offset* as a private CBIOS
anchor.  It saves and restores **both** the candidate byte and anchor,
avoiding permanent modifications to any populated RAM.  The CBIOS
uses segment 0400h, so the anchor and every candidate remain within
20-bit physical RAM, outside the 8088 boot ROM window.

`GETSEGT` still returns a pointer in BX to the existing one-entry
Memory Region Table (MRT).  `INIT` updates only its length; the region
always begins at segment 0800h (physical 08000h).  The resident
CCP/BDOS/CBIOS and stack are below this boundary.

| Installed RAM | TPA region segment | Length (paragraphs) | TPA size |
| --- | --- | --- | --- |
| 128 KiB | 0800h | 1800h | 96 KiB |
| 256 KiB | 0800h | 3800h | 224 KiB |
| 384 KiB | 0800h | 5800h | 352 KiB |
| 512 KiB | 0800h | 7800h | 480 KiB |
| 640 KiB | 0800h | 9800h | 608 KiB |
| 768 KiB | 0800h | B800h | 736 KiB |
| 896 KiB | 0800h | D800h | 864 KiB |
| 1024 KiB | 0800h | F700h | 988 KiB |

At 1024 KiB, the upper physical FF000h-FFFFFh is overlaid by the
8088 reset ROM.  Thus the MRT stops at segment FF00h instead of
extending to the 1 MiB address-space boundary.  The all-size check is
`python3 tests/check_ram_mrt.py build/cbios.bin` (also run by
`make test`).

**Hardware validation:** These probes rely on RAM mirroring, which
is implemented by the current FM-11 emulator.  Memory decode behavior
of every original FM-11 RAM expansion configuration has not yet been
verified on real hardware.  The source-level test models the emulator
decoder, not a live CPU or a booted CP/M-86 system.  Validate the
MRT via a guest command that calls `GETSEGT` (and by executing
programs above 512 KiB) before relying on the larger configurations
on a real FM-11.

## FM-11 devices

- Serial data/status: I/O ports FD06h and FD07h. The current emulator's
  shared USART8251 advertises TX-ready at status bit 0 and RX-ready at bit 1.
- Mini FDC: FD18h–FD1Fh (2D media). Standard FDC: FD30h–FD37h (2HD).
- 8088 card: 8237 DMA at ports 10h–23h; 8259 PIC at 00h/01h.
- 2D: 40 cylinders, 2 heads, 16 sectors per side, 256 bytes/sector.
- 2HD: 77 cylinders, 2 heads, 26 sectors per side, 256 bytes/sector.
  The special boot track has different sector sizes; IPL must account for it.
- CP/M physical sectors need 128-byte logical record deblocking.

The disk BIOS now provides DPH/DPB records for eight independent units:
A:..D: are 2D Mini-FDC drives 0..3 and E:..H: are standard-FDC 2HD
units 0..3. The logical drive mapping is independent of the boot source. The 2D filesystem parameters are:

- 32 CP/M records (128 bytes each) per logical side-track.
- 2 KiB allocation blocks; 152 data blocks numbered 0..151.
- 64 directory entries (one reserved allocation block).
- Four reserved side-tracks at the start (two cylinders, 16 KiB) to hold
  the 0x3E00-byte resident image.
- Per-drive CSV (16 bytes) and ALV (20 bytes), plus a shared 128-byte DIRBUF.

These parameters match the experimental raw 2D IPL image builder:
62 consecutive 256-byte sectors are placed at the beginning of the disk,
and the 64-entry empty CP/M directory starts after four reserved side-tracks.
The 128-byte READ/WRITE and read-modify-write paths have passed dedicated
emulator diagnostics. File-level filesystem behavior is not yet verified.

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

**2HD implementation:** Standard-FDC drives 0..3 use DMA channel 1,
FD30h..FD35h, 26 physical sectors per side-track and 52 CP/M records.
The 2HD DPB uses 4-KiB blocks (DSM=242, EXM=3), four reserved
side-tracks and separate CSV/ALV for E:..H:. Physical sector I/O uses
the same 256-byte bounce and 128-byte read/modify/write paths as 2D.
The 2HD boot image has 26x128-byte FM records on C0/H0, a 512-byte
IPL, and 62x256-byte resident sectors from C0/H1 onward. The 2HD
CBIOS variant starts the CCP on E: rather than A:.

**Limitations:** Full emulator-level runtime validation of CP/M-86
2HD boot and all eight drives is still outstanding.  Each record write
performs a physical read and write.  No retry, media-change detection,
or real-hardware timing validation is implemented.  The bounce buffer
is checked against the 8237 64 KiB page boundary, and the caller DMA
offset is checked for 128-byte segment wrapping.  An IPL must
establish the final resident segment and validate memory ownership.

The 2D IPL first-stage ROM and image generator are present. Next verify
actual cold boot through INIT, the CCP/BDOS core, and filesystem access,
then verify all additional 2D/2HD units and the 2HD boot image in the emulator.

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
