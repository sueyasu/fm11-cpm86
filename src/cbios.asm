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
    xor bx,bx             ; no drives present until FM-11 FDC port is added
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
; Memory region table is provisional and must be validated before boot.
mrt:
    db 1
    dw 0x0800,0x7800

; Pad to the fixed 0x1900-byte CBIOS image size.
times BIOS_SIZE - ($ - $) db 0
