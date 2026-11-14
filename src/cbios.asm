; FM-11 CP/M-86 v1.1 initial CBIOS scaffold.
; Resident core ABI and vector layout originate from sueyasu/pc98_cpm86.
; Only the 8251 console is implemented. Disk services intentionally fail.
; This is NOT a bootable BIOS yet; do not mistake the provisional DPH for media.
cpu 8086
bits 16
org 0x2500
bios_start:

SER_DATA     equ 0xFD06
SER_STATUS   equ 0xFD07
SER_RX_READY equ 0x02
SER_TX_READY equ 0x01
BIOS_SIZE    equ 0x1900
BIOS_WORK    equ 0x3E00
BIOS_STACK   equ BIOS_WORK+0x0300
BDOS_INT     equ 0x00E0
BDOS_OFFSET  equ 0x0B06

; CP/M-86 BIOS jump vector: same ordering as the PC-98 reference.
    jmp near INIT
    jmp near WBOOT
    jmp near CONST
    jmp near CONIN
    jmp near CONOUT
    jmp near LISTOUT
    jmp near PUNCH
    jmp near READER
    jmp near HOME
    jmp near SELDSK
    jmp near SETTRK
    jmp near SETSEC
    jmp near SETDMA
    jmp near READ
    jmp near WRITE
    jmp near LISTST
    jmp near SECTRAN
    jmp near SETDMAB
    jmp near GETSEGT
    jmp near GETIOBF
    jmp near SETIOBF

    times 15 db 0
    dw 0                  ; compatibility PFK table (not yet implemented)
    dw cur_disk
    dw 0                  ; serial compatibility vector
    db 0x10, 0x33
    dw 0                  ; fixed disk sector memory compatibility
    dw 0                  ; CRT mode compatibility

INIT:
    cli
    mov ax,cs
    mov ss,ax
    mov sp,BIOS_STACK
    mov ds,ax
    mov es,ax
    cld
    push ds
    xor ax,ax
    mov ds,ax
    mov word [BDOS_INT*4],BDOS_OFFSET
    mov ax,cs
    mov word [BDOS_INT*4+2],ax
    pop ds
    mov dx,SER_STATUS
    mov al,0x4E           ; asynchronous, 8 data bits, no parity, 1 stop
    out dx,al
    mov al,0x37           ; receive/transmit enabled; no interrupt reliance
    out dx,al
    mov word [cur_track],0
    mov word [cur_sector],0
    mov word [dma_off],0x0080
    mov [dma_seg],cs
    mov si,hello
    call serial_puts
    sti
    jmp 0x0000           ; CCP cold entry in resident segment

WBOOT:
    jmp 0x0006           ; provisional: disk reload not implemented

CONST:
    mov dx,SER_STATUS
    in al,dx
    test al,SER_RX_READY
    mov al,0
    jz .done
    dec al               ; 0xFF means input available
.done:
    ret

CONIN:
    call CONST
    or al,al
    jz CONIN
    mov dx,SER_DATA
    in al,dx
    ret

CONOUT:
LISTOUT:
PUNCH:
    mov al,cl
    call serial_putc
    ret

READER:
    jmp CONIN

LISTST:
    mov al,0xFF
    ret

serial_putc:
    push ax
    mov dx,SER_STATUS
.wait:
    in al,dx
    test al,SER_TX_READY
    jz .wait
    pop ax
    mov dx,SER_DATA
    out dx,al
    ret

serial_puts:
    lodsb
    test al,al
    jz .done
    call serial_putc
    jmp serial_puts
.done:
    ret

HOME:
    mov word [cur_track],0
    ret

SELDSK:
    ; CL = logical drive (A:..D: are 2D units 0..3).
    ; DL bit 0 = 0 for first login, 1 for an already logged-in disk.
    ; DPH/DPB describes the media, but READ/WRITE still report an error
    ; until the direct FDC/8237 transport has been implemented.
    xor bx,bx
    cmp cl,4
    jae .absent
    xor ch,ch
    mov bx,cx
    shl bx,1
    mov bx,[dph_table+bx]
    mov [cur_disk],cl
.absent:
    ret

SETTRK:
    mov [cur_track],cx
    ret

SETSEC:
    mov [cur_sector],cx
    ret

SETDMA:
    mov [dma_off],cx
    ret

SETDMAB:
    mov [dma_seg],cx
    ret

READ:
WRITE:
    mov al,1              ; CP/M-86 BIOS status: error, not success
    ret

SECTRAN:
    mov bx,cx             ; identity translation
    ret

GETSEGT:
    mov bx,mrt
    ret

GETIOBF:
    mov al,[iobyte]
    ret

SETIOBF:
    mov [iobyte],cl
    ret

hello db 'FM-11 CP/M-86 BIOS: serial initialized',13,10,0
cur_disk db 0
iobyte db 0
cur_track dw 0
cur_sector dw 0
dma_off dw 0x80
dma_seg dw 0
; CP/M-86 disk parameter headers.  Four independent 2D drives are
; advertised at A:..D:.  Each DPH is 16 bytes, with private CSV/ALV.
; See docs/architecture.md for the provisional 2D filesystem layout.
dph_table:
    dw dph0,dph1,dph2,dph3

dph0:
    dw 0,0,0,0
    dw dirbuf,dpb_2d,csv0,alv0
dph1:
    dw 0,0,0,0
    dw dirbuf,dpb_2d,csv1,alv1
dph2:
    dw 0,0,0,0
    dw dirbuf,dpb_2d,csv2,alv2
dph3:
    dw 0,0,0,0
    dw dirbuf,dpb_2d,csv3,alv3

; 40 cylinders * 2 sides * 16 sectors * 256 bytes = 320 KiB.
; One CP/M logical track is one side: 32 * 128-byte records.
; Reserve two side-tracks; 78 * 4 KiB / 2 KiB = 156 blocks.
dpb_2d:
    dw 32                 ; SPT: 128-byte records per side-track
    db 4,15,1             ; BSH, BLM, EXM (DSM < 256, 2 KiB blocks)
    dw 155                ; DSM: blocks 0..155
    dw 63                 ; DRM: 64 directory entries
    db 0x80,0             ; AL0/AL1: one directory block reserved
    dw 16                 ; CKS: (DRM+1)/4
    dw 2                  ; OFF: two reserved side-tracks

dirbuf: times 128 db 0
csv0: times 16 db 0
csv1: times 16 db 0
csv2: times 16 db 0
csv3: times 16 db 0
alv0: times 20 db 0
alv1: times 20 db 0
alv2: times 20 db 0
alv3: times 20 db 0

; Memory region table is provisional and must be validated before boot.
mrt:
    db 1
    dw 0x0800,0x7800

; Pad to the fixed 0x1900-byte CBIOS image size.
times BIOS_SIZE - ($ - $$) db 0
