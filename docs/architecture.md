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

CBIOS `INIT` calls `init_mrt` before entering CCP. With the FM-11
emulator's configurable RAM address decoder, memory not populated above
the installed capacity aliases RAM at the beginning of the address
space. The routine checks **8 KiB boundaries** from 64 KiB through
1016 KiB, supporting all installed capacities from 128 KiB to 1 MiB
that are multiples of 8 KiB (including 192 KiB).

The probe uses a saved byte at physical `0000:0500` and a matching
offset in each candidate 8 KiB window (first `1000:0500`, last
`FE00:0500`). These addresses avoid both the resident CP/M system
(physical 04000h-07FFFh) and the reset ROM (physical FF000h-FFFFFh).
Each candidate must read back **both 55h and AAh** without modifying
the anchor (which is held at 5Ah). The first failed readback **or**
the first mirror marks the end of usable contiguous RAM. Both the
probe candidate byte and the anchor byte are restored before
returning, even on alias detection; DS/ES are also restored.

In particular, absent physical RAM that ignores writes and returns
fixed zero or FFh no longer appears to be installed. The probe assumes
at least 128 KiB installed, matching supported FM-11 emulator
configurations. Other electrical open-bus behaviors still require
testing on real hardware.

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
extending to the 1 MiB address-space boundary.  The 113-capacity test (mirrored, zero-filled and FFh open-bus models) is
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

## 8088 native screen and keyboard

The FM-11 8088 card exposes the same display-subsystem I/O controls
as the 6809 main card. `src/cbios_local_console.inc` implements the
same HALT/mailbox transaction used by the NitrOS-9 `fm11console`
driver and the CP/M-80 I/O server, translated to 8086 I/O instructions:

1. Poll `IN AL,FD05h` until bit 7 clears (subsystem ready).
2. `OUT FD05h,80h` to halt the display CPU; poll for bit 7 set.
3. Set `FC80h=0, FC81h=0, FC82h=command, FC83h=parameter,
   FC84h=0`.
4. `OUT FD05h,00h` to resume the subsystem; poll for bit 7 clear.
5. For `INKEY 2`, read `FC83h` (extended-status) and `FC84h`
   (ASCII or extended keycode).

The transaction always writes bit 0 of `FD05h` as zero, so it never
requests an optional CPU-card bus-master switch. Each handshake
has a bounded timeout. `CONST` caches characters for `CONIN`;
arrow-key codes 0116h..0119h become ESC-[A..D and DEL 0114h is
mapped to 7Fh. The display emits native FM-11 characters through
subsystem command 12h. The BIOS keeps its 21-entry vector order,
CBIOS 1900h-byte length and BOOT_DRIVE patch immediate position.

Native local console is the default CBIOS build; `CONSOLE_LOCAL=0`
at NASM assembly time selects the original serial path. The 2D and
HDD reset ROMs also skip the optional serial-PTY input gate in the
local build. `LISTOUT` and `PUNCH` continue using USART0.

This is **native-character mode** rather than the more comprehensive
NitrOS-9 ANSI/VT100 parser. The emulator's 8088 `Main8088Bus`
routes `FC80h-FCFFh` to `MainBoard::displaySubsystem` and
`FD05h` to the same subsystem control used by 6809. Live SDL
screen/keyboard verification remains outstanding.

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
A physical-sector miss reads a complete 256-byte sector into
`fdc2d_buffer`. The cache key consists of drive, logical side-track and
0-based physical-sector index, shared across 2D/2HD/HDD.
A hit on either logical 128-byte half reuses the buffer without another
physical READ. A WRITE replaces only the selected half and **always**
issues a complete 256-byte physical WRITE (write-through), retaining
the other half. A failed WRITE invalidates the cache; a failed READ never
publishes a valid key. A first-login SELDSK (DL bit 0 clear), INIT and
WBOOT invalidate it as well. This is a one-sector global cache, not
yet a per-drive track cache; it never holds dirty data and needs no flush.

The common deblocking/transport layer lives in `src/cbios_sector_cache.inc`;
`fdc2d_read/write` and `hdd_read/write` remain the physical transport.
The dedicated CBIOS self-test checks paired record READ hits, zero
extra physical READs on a cached WRITE, one physical WRITE on commit,
re-login invalidation and original-data restoration.  `make test`
checks static invariants and the image/CBIOS layout; the guest self-test
must still be run on a disposable disk to validate real FDC traffic.
Both logical operations return AX=0 on success and AX=1 on error.

**2HD implementation:** Standard-FDC drives 0..3 use DMA channel 1,
FD30h..FD35h, 26 physical sectors per side-track and 52 CP/M records.
The 2HD DPB uses 4-KiB blocks (DSM=242, EXM=3), four reserved
side-tracks and separate CSV/ALV for E:..H:. Physical sector I/O uses
the same 256-byte bounce and 128-byte read/modify/write paths as 2D.
The 2HD boot image has 26x128-byte FM records on C0/H0, a 512-byte
IPL, and 62x256-byte resident sectors from C0/H1 onward. The 2HD
CBIOS variant starts the CCP on E: rather than A:.

**Limitations:** Full emulator-level runtime validation of CP/M-86
2HD boot and all eight drives is still outstanding.  A record WRITE always performs a physical WRITE but a preceding
physical READ is avoided when its sector is cached. No retry, automatic
media-change detection, or real-hardware timing validation is implemented.  The bounce buffer
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
