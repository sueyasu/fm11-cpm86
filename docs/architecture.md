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
retains the CBIOS 21-entry jump table, 
The 2D and 2HD disk IPLs load this resident image at segment
0400h and enters CBIOS INIT at 0400:2500. The initial BIOS stack tops
out at 0400:4000 (physical 08000h), below the TPA base at segment 0800h. The CCP/BDOS boot has been verified in the emulator.

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
| 128 KiB | 0800h | 1400h | 80 KiB |
| 256 KiB | 0800h | 3400h | 208 KiB |
| 384 KiB | 0800h | 5400h | 336 KiB |
| 512 KiB | 0800h | 7400h | 464 KiB |
| 640 KiB | 0800h | 9400h | 592 KiB |
| 768 KiB | 0800h | B400h | 720 KiB |
| 896 KiB | 0800h | D400h | 848 KiB |
| 1024 KiB | 0800h | F300h | 972 KiB |

At 1024 KiB, the upper physical FF000h-FFFFFh is overlaid by the
8088 reset ROM.  Thus the MRT stops at segment FF00h instead of
extending to the 1 MiB address-space boundary.  The 113-capacity test (mirrored, zero-filled and FFh open-bus models) is
`python3 tests/check_ram_mrt.py build/cbios.bin` (also run by
`make test`).

**Hardware validation:** These probes detect both RAM mirroring and failed write/readback.  Memory decode behavior
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
at NASM assembly time selects the original serial path. The HDD reset ROM also skips the optional serial-PTY input gate in the
local build. `LISTOUT` and `PUNCH` continue using USART0.

The local output now also translates the supported ANSI/VT100 sequences through src/cbios_ansi.inc. The emulator's 8088 `Main8088Bus`
routes `FC80h-FCFFh` to `MainBoard::displaySubsystem` and
`FD05h` to the same subsystem control used by 6809. Real hardware validation remains necessary.

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
emulator diagnostics. File-level operation has also been exercised in the emulator.

The initial 2D physical-sector transport is now present in `src/cbios.asm`
as `fdc2d_read` and `fdc2d_write`.  Both use the Mini FDC registers
FD18h/FD19h/FD1Ah/FD1Ch/FD1Dh and 8237 channel 0 (10h/11h/18h/1Ah/
1Bh/1Ch/20h).  The transfer is exactly 256 bytes into or out of the
BIOS-local `fdc2d_buffer`.  Entry registers are AL=drive, CH=cylinder,
DH=head, CL=physical-sector (1-based); CF reports success/failure.
The implementation checks DMA terminal count and FDC completion status,
and masks CH0 on return. DMA CH0 is owned exclusively during the call.

**Logical I/O and track write-back cache:** CP/M-86 `READ`/`WRITE`
use 128-byte records (2D: 32 per logical side-track; 2HD: 52;
HDD: 64). The physical sector is `record / 2` and the half-sector
offset is `(record & 1) * 128`. The physical transport remains
unchanged: `fdc2d_read/write` and `hdd_read/write` issue 256-byte
DMA operations via the resident `fdc2d_buffer`.

`src/cbios_track_cache.inc` implements **two shared 8 KiB windows**.
Each window holds one logical side/head-track, identified by CP/M drive
and track. Per-window **32-bit valid and dirty bitmaps** track physical
sectors individually; only accessed sectors are loaded, and only dirty
sectors are written on flush. The windows are allocated at the top of
the detected RAM and removed from the MRT TPA during `INIT`.
Thus 128 KiB RAM has **80 KiB TPA** instead of 96 KiB, and 1 MiB
(with the 4 KiB ROM overlay) has **972 KiB TPA** instead of 988 KiB.
Two windows let PIP alternate between source and destination tracks
without replacing either window.

**Write-back / consistency policy:** Every logical WRITE updates its
128-byte half inside the resident track window and marks that physical
sector dirty; a normal WRITE does not immediately access the disk.
Dirty sectors are written when a window is evicted, on `WBOOT`, on
first-login `SELDSK` (after which windows are invalidated), and on
**directory WRITE (`CL=1`)**. Before a directory WRITE, pending file
data on both windows is flushed; then the modified directory record is
written and the resulting dirty sector is flushed before reporting
success. This ordering avoids persisting a new directory entry before
its data blocks. Failed physical writes retain the dirty bitmap, prevent
unsafe eviction, and return an I/O error. WBOOT reports a failed flush on the active console and halts rather than discarding dirty data. The special
WRITE type `CL=2` (first record of unallocated block) still reads the
256-byte physical sector before modifying it, so its other half
remains intact.

**Private cache API:** Fixed FAR entries at 0400:3DD8 (CACHE_SYNC)
and 0400:3DDC (CACHE_RESET) return CF=1 on failure. CACHE_RESET
invalidates windows only after successful synchronization. FORMAT calls
CACHE_RESET before direct disk I/O. Media changes still require the
operator to follow the procedure in the main README.

Physical FDD READ/WRITE attempts are limited to ten and MDC attempts
to three, including the initial command. DMA is reprogrammed for each
attempt. A controller that remains busy/not command-ready terminates
the operation without another command. No controller reset or FDD
recalibration is performed.

`make test` checks the source invariants and fixed CBIOS image layout;
the optional CBIOS self-test additionally checks two-window retention,
paired 128-byte cache hits, delayed physical WRITE counts, flush and
on-disk restoration on a disposable image. The hardware/emulator
integration path still requires guest execution. `READ` and `WRITE`
return AX=0 on success and AX=1 on error.

**Physical floppy positioning:** A:..H: each have an independent cached
physical cylinder (FFh = unknown). The CBIOS masks the selected 8237 DMA
channel, selects the drive, performs RESTORE if its position is unknown,
restores the shared FDC TRACK register from the saved drive position, and
issues SEEK only when the desired cylinder differs. Type I completion is
bounded and checks BUSY and seek/not-ready errors. Failed attempts forget
that drive's cylinder; cold initialization and successful cache reset or
media re-login forget all eight positions. The latter allows direct-I/O
utilities such as FORMAT to move heads without leaving stale CBIOS state.
Logical HOME/SETTRK remain deferred; positioning occurs at physical I/O,
including cache write-back to a drive other than the current BDOS drive.

**2HD implementation:** Standard-FDC drives 0..3 use DMA channel 1,
FD30h..FD35h, 26 physical sectors per side-track and 52 CP/M records.
The 2HD DPB uses 4-KiB blocks (DSM=242, EXM=3), four reserved
side-tracks and separate CSV/ALV for E:..H:. Physical sector I/O uses
the same 256-byte bounce and 128-byte read/modify/write paths as 2D.
The 2HD boot image has 26x128-byte FM records on C0/H0, a 512-byte
IPL, and 62x256-byte resident sectors from C0/H1 onward. The 2HD
CBIOS variant starts the CCP on E: rather than A:.

**Limitations:** Full emulator runtime verification of all nine drives
and real hardware still needs to be performed. The track cache does not
provide automatic media-change detection or coordination with direct
controller access, and only two tracks are resident at once. The DMA
bounce buffer is checked against 8237 64 KiB page boundaries, and the
caller DMA offset is checked for 128-byte wrapping.

2D, 2HD and whole-HDD boot images are supported. Testing every drive and original hardware configuration remains necessary.

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
