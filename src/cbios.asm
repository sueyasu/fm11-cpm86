; FM-11 CP/M-86 v1.1 experimental CBIOS.
; Resident core ABI and vector layout originate from sueyasu/pc98_cpm86.
; A:..D: 2D, E:..H: 2HD, I: whole MDC HDD, 128-byte records.
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
%ifndef BOOT_DRIVE
%define BOOT_DRIVE 0             ; 2D=A:, 2HD=E:, HDD=I: (8)
%endif
BIOS_WORK    equ 0x3E00
BIOS_STACK   equ BIOS_WORK+0x0200 ; 0400h:4000h ends below TPA 0800h
BDOS_INT     equ 0x00E0
BDOS_OFFSET  equ 0x0B06

; CP/M-86 BIOS jump vector: same ordering as the PC-98 reference.
    jmp strict near INIT
    jmp strict near WBOOT
    jmp strict near CONST
    jmp strict near CONIN
    jmp strict near CONOUT
    jmp strict near LISTOUT
    jmp strict near PUNCH
    jmp strict near READER
    jmp strict near HOME
    jmp strict near SELDSK
    jmp strict near SETTRK
    jmp strict near SETSEC
    jmp strict near SETDMA
    jmp strict near READ
    jmp strict near WRITE
    jmp strict near LISTST
    jmp strict near SECTRAN
    jmp strict near SETDMAB
    jmp strict near GETSEGT
    jmp strict near GETIOBF
    jmp strict near SETIOBF

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
    ; The medium-specific IPL/CBIOS build determines the cold boot drive.
    mov cx,BOOT_DRIVE
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
    ; CL=0..7: A:..D: 2D units 0..3; E:..H: 2HD units 0..3.
    ; DL bit 0 = 0 on first login, 1 if previously logged in.
    xor bx,bx
    cmp cl,9
    jae .absent
    cmp cl,8
    jne .table
    push cx
    call hdd_sense
    pop cx
    jc .absent
.table:
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

; CP/M-86 128-byte record I/O: 2D (32 records/side-track) or
; 2HD (52 records/side-track).  All eight drives are independent.
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
    cmp byte [cur_disk],8
    je .hdd_track
    ja .invalid
    cmp byte [cur_disk],4
    jb .check_2d_track
    cmp bx,154              ; 2HD: 77 cylinders * 2 side-tracks
    jmp .track_checked
.check_2d_track:
    cmp bx,80               ; 2D: 40 cylinders * 2 side-tracks
    jmp .track_checked
.hdd_track:
    cmp bx,[hdd_total_tracks]
.track_checked:
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
    cmp byte [cur_disk],8
    je .hdd_sector
    cmp byte [cur_disk],4
    jb .check_2d_sector
    cmp bx,52               ; 2HD: 26 * 2 logical records
    jmp .sector_checked
.check_2d_sector:
    cmp bx,32               ; 2D: 16 * 2 logical records
    jmp .sector_checked
.hdd_sector:
    cmp bx,64
.sector_checked:
    jae .invalid
    mov bx,[dma_off]
    cmp bx,0xff80           ; prevent a 128-byte segment wrap
    ja .invalid
    jmp .valid
.invalid:
%ifdef CBIOS_SELFTEST
    mov byte [st_rw_path],2      ; input rejected before disk access
%endif
    jmp .error
.valid:
%ifdef CBIOS_SELFTEST
    mov byte [st_rw_path],3      ; input accepted; disk access follows
%endif
    cmp byte [cur_disk],8
    jne .floppy_read
    mov bx,[cur_sector]
    and bx,1
    call hdd_read
    jc .error
    jmp .copy_record
.floppy_read:
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
.copy_record:
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
    cmp al,8
    jne .floppy_write
    call hdd_write
    jc .error
    jmp .success
.floppy_write:
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
; Common 2D/2HD 256-byte physical-sector transport, direct 8088 path.
;
; Entry for both functions:
;   AL = CP/M drive 0..7; CH = cylinder; DH = head;
;   CL = physical sector number. 2D uses CH0/FD18, 2HD CH1/FD30.
;   Fixed DMA buffer = CS:fdc2d_buffer; preserves all general registers.
; Return CF=0 for one complete 256-byte transfer, CF=1 on error.
;
; These are physical 256-byte transfers used by the CP/M-86
; READ/WRITE entries above. Only the selected DMA channel is programmed.
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

    mov bx,ax                ; BL=logical drive, BH=8237 CH0 mode
    mov byte [fdc_channel],0
    cmp bl,8
    jae .invalid
    cmp dh,1
    ja .invalid
    cmp cl,1
    jb .invalid
    cmp bl,4
    jb .validate_2d
    sub bl,4                 ; E:..H: -> standard FDC units 0..3
    mov byte [fdc_channel],1
    inc bh                   ; CH0 mode 44/48 -> CH1 45/49
    cmp ch,77
    jae .invalid
    cmp cl,26
    ja .invalid
    jmp .validated
.validate_2d:
    cmp ch,40
    jae .invalid
    cmp cl,16
    ja .invalid
    jmp .validated
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

    mov dx,0x1a             ; mask selected 8237 channel
    mov al,4
    add al,[fdc_channel]
    out dx,al
    mov dx,0x1c             ; reset 8237 address/count flip-flop
    xor al,al
    out dx,al

    mov dx,0x10             ; CH0 address=10h, CH1 address=12h
    cmp byte [fdc_channel],0
    je .address_port
    mov dl,0x12
.address_port:
    mov ax,si
    out dx,al
    mov al,ah
    out dx,al

    mov dx,0x11             ; CH0 count=11h, CH1 count=13h
    cmp byte [fdc_channel],0
    je .count_port
    mov dl,0x13
.count_port:
    mov al,0xff
    out dx,al
    xor al,al
    out dx,al

    mov dx,0x20             ; CH0 bank=20h, CH1 bank=21h
    cmp byte [fdc_channel],0
    je .bank_port
    mov dl,0x21
.bank_port:
    mov ax,di
    out dx,al
    mov dx,0x1b             ; transfer direction, selected single mode
    mov al,bh
    out dx,al
    mov dx,0x18             ; discard any previous terminal-count latch
    in al,dx

    mov dx,0xfd19           ; 2D FD19/1A/1C/1D; 2HD FD31/32/34/35
    cmp byte [fdc_channel],0
    je .track_port
    mov dl,0x31
.track_port:
    mov al,ch
    out dx,al
    inc dx                  ; FD1A: sector
    mov al,cl
    out dx,al
    mov dx,0xfd1c           ; FD1C or FD34: side
    cmp byte [fdc_channel],0
    je .side_port
    mov dl,0x34
.side_port:
    mov ax,bp                ; original caller DH, not port high byte FDh
    mov al,ah
    out dx,al
    inc dx                  ; FD1D: physical drive
    mov al,bl
    out dx,al

    mov dx,0x1a             ; unmask selected channel
    mov al,[fdc_channel]
    out dx,al
    mov dx,0xfd18
    cmp byte [fdc_channel],0
    je .command_port
    mov dl,0x30
.command_port:
    mov al,0x80
    cmp bh,0x44
    je .start
    cmp bh,0x45
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
    in al,dx                ; 8237 terminal count (CH0=bit0, CH1=bit1)
    cmp byte [fdc_channel],0
    je .check_tc0
    test al,2
    jz .fail
    jmp .tc_ok
.check_tc0:
    test al,1
    jz .fail
.tc_ok:
    clc
    jmp .finish
.fail:
    stc
.finish:
    pushf
    mov dx,0x1a             ; leave selected DMA channel masked
    mov al,4
    add al,[fdc_channel]
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

%include "cbios_hdd.inc"

; DMA bounce buffer, never exposed as a logical CP/M record.
fdc_channel db 0
fdc2d_buffer: times 256 db 0

; Eight physical drives: A:..D: 2D/CH0, E:..H: 2HD/CH1.
; Every DPH has private CSV/ALV, using a shared 128-byte directory buffer.
; See docs/architecture.md for the provisional 2D filesystem layout.
dph_table:
    dw dph0,dph1,dph2,dph3,dph4,dph5,dph6,dph7,dph8

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
dph4:
    dw 0,0,0,0
    dw dirbuf,dpb_2hd,csv4,alv4
dph5:
    dw 0,0,0,0
    dw dirbuf,dpb_2hd,csv5,alv5
dph6:
    dw 0,0,0,0
    dw dirbuf,dpb_2hd,csv6,alv6
dph7:
    dw 0,0,0,0
    dw dirbuf,dpb_2hd,csv7,alv7
dph8:
    dw 0,0,0,0
    dw dirbuf,dpb_hdd,0,alv8

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

; 2HD: 77 cylinders x 2 heads x 26 x 256-byte sectors.
; Four side-tracks (two cylinders) reserved for IPL and resident image.
; 150 remaining side-tracks = 998400 bytes -> 243 full 4 KiB blocks.
; DSM=242 keeps 8-bit allocation entries (16 pointers per directory entry).
dpb_2hd:
    dw 52                 ; SPT: 26 physical sectors x 2 records
    db 5,31,3             ; BSH=5 4 KiB, BLM=31, EXM=3 (DSM < 256)
    dw 242                ; DSM: block numbers 0..242
    dw 63                 ; DRM: 64 directory entries
    db 0x80,0             ; AL0/AL1: block 0 reserved for directory
    dw 16                 ; CKS
    dw 4                  ; OFF: four reserved side-tracks

; I: whole HDD, 32x256 physical sectors per head-track.
; 64 logical 128-byte records; reserve first cylinder (OFF=heads).
; 16-KiB allocation blocks, 512 directory entries; sensed DSM.
dpb_hdd:
    dw 64
    db 7,127,7
    dw 0                     ; DSM filled from sense
    dw 511                   ; 512 directory entries
    db 0x80,0
    dw 0                     ; no checksum vector on fixed disk
    dw 0                     ; OFF filled from heads

dirbuf: times 128 db 0
csv0: times 16 db 0
csv1: times 16 db 0
csv2: times 16 db 0
csv3: times 16 db 0
csv4: times 16 db 0
csv5: times 16 db 0
csv6: times 16 db 0
csv7: times 16 db 0
alv0: times 20 db 0
alv1: times 20 db 0
alv2: times 20 db 0
alv3: times 20 db 0
alv4: times 31 db 0
alv5: times 31 db 0
alv6: times 31 db 0
alv7: times 31 db 0
alv8: times 514 db 0        ; maximum ~4103 allocation blocks

; Memory region table is provisional and must be validated before boot.
mrt:
    db 1
    dw 0x0800,0x7800

; Pad the CBIOS itself (not the optional 0x2500-byte preceding core).
times BIOS_SIZE - ($ - bios_start) db 0
