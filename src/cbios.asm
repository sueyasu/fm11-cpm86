; FM-11 CP/M-86 v1.1 experimental CBIOS.
; Resident core ABI and vector layout originate from sueyasu/pc98_cpm86.
; 8251 serial console and Mini-FDC 2D 128-byte READ/WRITE are implemented.
; IPL/cold-boot and file-level CP/M-86 compatibility are not yet verified.
cpu 8086
bits 16
%ifndef CBIOS_EMBEDDED
org 0x2500
%endif
bios_start:

SER_DATA     equ 0xFD06
SER_STATUS   equ 0xFD07
SER_RX_READY equ 0x02
SER_TX_READY equ 0x01
BIOS_SIZE    equ 0x1900
BIOS_WORK    equ 0x3E00
BIOS_STACK   equ BIOS_WORK+0x0200 ; 0400h:4000h ends below TPA 0800h
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
    ; The IPL has already configured USART0. Do NOT reinitialize it:
    ; on the original emulator a command write that drops DTR (bit 1)
    ; calls CNamedPipe::DoClose() and disconnects the active terminal.
    ; In particular the old 00h/40h reset sequence is unsafe here.
    ; Leave MODE, CMD and DTR untouched throughout the CBIOS handoff.
    mov word [cur_track],0
    mov word [cur_sector],0
    mov word [dma_off],0x0080
    mov [dma_seg],cs
    mov si,hello
    call serial_puts

    ; Match the CP/M-86 v1.1 cold-start ABI from pc98_cpm86:
    ; BDOS CURDRV resides at offset 24B7h in the common system segment.
    ; The CCP cold entry also expects the boot drive in CL.
    ; We currently boot only from the Mini-FDC unit 0 (A:).
    xor cx,cx
    mov byte [cur_disk],cl
    mov byte [0x24b7],cl
    sti
%ifdef CBIOS_SELFTEST
    jmp selftest_entry   ; diagnostic build: never enter CCP/BDOS
%else
    jmp 0x0000           ; CCP cold entry in resident segment
%endif

WBOOT:
    jmp 0x0006           ; provisional: disk reload not implemented

CONST:
    ; Preserve DX: unlike the PC-98 immediate-port IN, FM-11 I/O
    ; addresses require the DX form.  BDOS/CCP may hold live data in DX.
    push dx
    mov dx,SER_STATUS
    in al,dx
    test al,SER_RX_READY
    mov al,0
    jz .done
    dec al               ; 0xFF means input available
.done:
    pop dx
    ret

CONIN:
    call CONST
    or al,al
    jz CONIN
    push dx
    mov dx,SER_DATA
    in al,dx
    pop dx
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
    push dx
    mov dx,SER_STATUS
.wait:
    in al,dx
    test al,SER_TX_READY
    jz .wait
    pop dx
    pop ax
    ; DX is still needed for data-port OUT: preserve it until return.
    push dx
    mov dx,SER_DATA
    out dx,al
    pop dx
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
    ; The current emulator supports physical Mini-FDC unit 0 for I/O.
    ; DPH entries for B:..D: remain provisional.
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

; CP/M-86 128-byte record I/O for Mini FDC (2D).
; A CP/M track represents one physical side (32 records).
; The current emulator supports physical Mini FDC unit 0 only.
; Each write reads the whole physical sector before changing one half.
READ:
%ifdef CBIOS_SELFTEST
    mov byte [cs:st_rw_entry],1 ; proves the direct CALL reached READ
%endif
    xor ah,ah               ; read
    jmp short rw_2d
WRITE:
    mov ah,1                ; write
rw_2d:
%ifdef CBIOS_SELFTEST
    mov byte [cs:st_rw_entry],2 ; proves JMP reached common entry
%endif
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov bp,ax               ; preserve read/write flag in AH
    push cs
    pop ds                  ; BIOS variables and bounce buffer use CS
    push cs
    pop es
%ifdef CBIOS_SELFTEST
    mov byte [cs:st_rw_entry],3 ; segment setup/prologue completed
    mov [cs:st_rw_ds],ds
%endif

    mov bx,[cur_track]
    cmp bx,80               ; 40 cylinders * 2 side-tracks
%ifdef CBIOS_SELFTEST
    ; Diagnostic only. PUSHF/POP memory preserve CMP FLAGS for JAE;
    ; report whether the actual instruction sees the expected BX/CF/ZF.
    mov [st_rw_track_bx],bx
    pushf
    pop word [st_rw_track_flags]
    mov byte [st_rw_path],1
%endif
    jae .invalid
    mov bx,[cur_sector]
    cmp bx,32               ; 128-byte logical records, numbered 0..31
    jae .invalid
    mov bx,[dma_off]
    cmp bx,0xff80           ; prevent a 128-byte segment wrap
    ja .invalid
    cmp byte [cur_disk],0   ; Mini FDC emulator currently models unit 0
    jne .invalid
    jmp short .valid
.invalid:
%ifdef CBIOS_SELFTEST
    mov byte [st_rw_path],2      ; input rejected before disk access
%endif
    jmp .error
.valid:
%ifdef CBIOS_SELFTEST
    mov byte [st_rw_path],3      ; input accepted; disk access follows
%endif
    ; Translate side-track and logical record to physical CHS.
    mov bx,[cur_track]
    mov dx,bx
    and dl,1
    mov dh,dl               ; physical head = track & 1
    shr bx,1
    mov ch,bl               ; cylinder = track / 2
    mov bx,[cur_sector]
    mov cl,bl
    shr cl,1
    inc cl                  ; physical sector = record / 2 + 1
    and bx,1
    mov al,[cur_disk]
    call fdc2d_read
    jc .error

    ; BX is preserved by the physical sector routine: 0/1 half selector.
    ; 8086 only permits an immediate shift count of one.
    ; Do not use CL here: it still holds the sector number for WRITE.
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1                ; byte offset of the selected half
    cld
    test bp,0x0100
    jnz .write_half

    ; READ: BIOS buffer -> selected caller DMA segment:offset.
    mov si,fdc2d_buffer
    add si,bx
    mov di,[dma_off]
    mov ax,[dma_seg]
    mov es,ax
    mov cx,64
    rep movsw
    jmp short .success

.write_half:
    ; WRITE: caller DMA -> BIOS buffer, retaining the opposite half.
    ; Preserve CHS across the 128-byte memory copy.
    push cx
    push dx
    mov si,[dma_off]
    mov di,fdc2d_buffer
    add di,bx
    mov ax,[dma_seg]
    mov ds,ax
    mov cx,64
    rep movsw
    pop dx
    pop cx
    push cs
    pop ds
    mov al,[cur_disk]
    call fdc2d_write
    jc .error
.success:
    xor ax,ax               ; CP/M-86 success: clear full AX, not only AL.
    jmp short .done
.error:
    mov ax,1                ; CP/M-86 disk error: clear AH as well.
.done:
%ifdef CBIOS_SELFTEST
    mov [st_rw_done_ax],ax       ; status before saved registers are restored
%endif
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
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
; ----------------------------------------------------------------------
; 2D physical-sector transport (256 bytes), preliminary direct 8088 path.
;
; Entry for both functions:
;   AL = physical drive (currently 0 only), CH = cylinder (0..39),
;   DH = head (0..1), CL = physical sector number (1..16).
;   Fixed DMA buffer = CS:fdc2d_buffer; preserves all general registers.
; Return CF=0 for one complete 256-byte transfer, CF=1 on error.
;
; These are physical 256-byte transfers used by the CP/M-86
; READ/WRITE entries above. DMA CH0 and Mini FDC are temporarily exclusive.
; ----------------------------------------------------------------------
fdc2d_read:
    mov ah,0x44              ; CH0, single, I/O -> memory
    jmp fdc2d_transfer

fdc2d_write:
    mov ah,0x48              ; CH0, single, memory -> I/O

fdc2d_transfer:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bp,dx                ; preserve head in DH before DX becomes I/O port

    mov bx,ax                ; BL=drive, BH=8237 mode
    cmp bl,0                 ; emulator Mini FDC currently selects unit 0
    jne .invalid
    cmp ch,40
    jae .invalid
    cmp dh,1
    ja .invalid
    cmp cl,1
    jb .invalid
    cmp cl,16
    ja .invalid
    jmp short .validated
.invalid:
    jmp .bad               ; 8086 conditional branches have 8-bit reach
.validated:

    ; Convert the real-mode CS:offset into an 8237 bank:offset address.
    ; 256-byte transfer must not cross a 64 KiB DMA page boundary.
    mov ax,cs
    mov si,16
    mul si                   ; DX:AX = CS * 16
    add ax,fdc2d_buffer
    adc dx,0
    cmp ax,0xff00
    ja .invalid
    mov si,ax                ; 16-bit DMA address
    mov di,dx                ; DMA bank (bits 16..19)

    mov dx,0x1a             ; mask DMA channel 0 while programming
    mov al,4
    out dx,al
    mov dx,0x1c             ; reset 8237 address/count flip-flop
    xor al,al
    out dx,al

    mov dx,0x10             ; CH0 address, low byte then high byte
    mov ax,si
    out dx,al
    mov al,ah
    out dx,al

    mov dx,0x11             ; CH0 terminal count = 256 - 1
    mov al,0xff
    out dx,al
    xor al,al
    out dx,al

    mov dx,0x20             ; CH0 DMA bank
    mov ax,di
    out dx,al
    mov dx,0x1b             ; transfer direction, CH0 single mode
    mov al,bh
    out dx,al
    mov dx,0x18             ; discard any previous terminal-count latch
    in al,dx

    mov dx,0xfd19           ; FDC track
    mov al,ch
    out dx,al
    inc dx                  ; FD1A: sector
    mov al,cl
    out dx,al
    mov dx,0xfd1c           ; FD1C: side
    mov ax,bp                ; original caller DH, not port high byte FDh
    mov al,ah
    out dx,al
    inc dx                  ; FD1D: physical drive
    mov al,bl
    out dx,al

    mov dx,0x1a             ; unmask CH0
    xor al,al
    out dx,al
    mov dx,0xfd18
    mov al,0x80
    cmp bh,0x44
    je .start
    mov al,0xa0
.start:
    out dx,al

    ; Poll until FDC no longer indicates a transfer in progress.
    ; Fail closed on controller error and on a bounded poll timeout.
    mov cx,0xffff
.poll:
    in al,dx
    test al,0x10            ; Mini FDC error
    jnz .fail
    test al,0x02            ; transfer in progress
    jz .status_done
    loop .poll
    jmp .fail

.status_done:
    or al,al                ; success requires status = 0
    jnz .fail
    mov dx,0x18
    in al,dx                ; check 8237 CH0 terminal-count flag
    test al,1
    jz .fail
    clc
    jmp .finish
.fail:
    stc
.finish:
    pushf
    mov dx,0x1a             ; leave DMA CH0 masked
    mov al,4
    out dx,al
    popf
    jmp .restore
.bad:
    stc
.restore:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; DMA bounce buffer, never exposed as a logical CP/M record.
fdc2d_buffer: times 256 db 0

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
; Reserve four side-tracks for the 0x3E00-byte CP/M-86 resident
; image (62 physical sectors): 76 * 4 KiB / 2 KiB = 152 blocks.
dpb_2d:
    dw 32                 ; SPT: 128-byte records per side-track
    db 4,15,1             ; BSH, BLM, EXM (DSM < 256, 2 KiB blocks)
    dw 151                ; DSM: blocks 0..151
    dw 63                 ; DRM: 64 directory entries
    db 0x80,0             ; AL0/AL1: one directory block reserved
    dw 16                 ; CKS: (DRM+1)/4
    dw 4                  ; OFF: four reserved side-tracks (2 cylinders)

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

; Pad the CBIOS itself (not the optional 0x2500-byte preceding core).
times BIOS_SIZE - ($ - bios_start) db 0
