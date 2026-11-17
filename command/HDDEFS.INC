; HDDEFS.INC -- FM-11 CP/M-86 native MDC disk and partition ABI.
; One controller, one physical HDD, 256 bytes per physical record.
; WARNING: This is NOT the NEC PC-98 SCSI partition table format.
; The first physical cylinder is reserved.  Sector C0/H0/S31 stores
; the partition table; sectors C0/H0/S0..S30 are left untouched.
;
; 256-byte partition sector, all fields little-endian:
; +00..07 "FM11PT86" / +08 version 01 / +09 heads
; +10..11 cylinders / +12 SPT 32 / +13 entry-count 16
; +14..15 reserved / +16 sixteen 12-byte records:
;   +0 start cylinder u16, +2 cylinder count u16
;   +4 type 70h, +5 flags 00h, +6..11 reserved.
; Partitions start at >= cylinder 1, are non-overlapping, and each
; reserves its first cylinder for future IPL / 0x3E00 system image.
; No bootable HDD path is implemented until CBIOS/ROM IPL is extended.

BDOSINT        equ     0e0h
HD_PORT_CMD    equ     0fdc0h
HD_PORT_DATA   equ     0fdc1h
HD_PORT_SEL    equ     0fdc2h
HD_SENSE       equ     014h
HD_MODE        equ     011h
HD_READ        equ     022h
HD_WRITE       equ     023h
HD_DMA_CH      equ     2
HD_SPT         equ     32
HD_TABLE_SEC   equ     31
HD_ENTRIES     equ     16
HD_ENTRY_SIZE  equ     12
HD_ENT_BASE    equ     16
HD_PART_TYPE   equ     070h
HD_BUF_SIZE    equ     256
HD_DMA_LIMIT   equ     65280

