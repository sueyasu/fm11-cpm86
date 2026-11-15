; FM-11 CP/M-86 CBIOS in-place self-test (CBIOS_SELFTEST build only).
; Runs after INIT, instead of entering the unmodified CCP/BDOS core.
; Uses real CBIOS entry functions and a *disposable* disk image.
; CBIOS state resides in CS=DS=SS=0400h. The data buffers are in
; segment 0800h (TPA), which the test owns because CCP never runs.
;
; The WRITE test targets side-track 79, record 31. It reads and saves
; its original 128 bytes, writes a pattern, reads back and restores.
; NEVER use the self-test image as a valuable original floppy image.

%macro ST_CHECK_Z 0
    jz %%good
    jmp st_fail
%%good:
%endmacro
%macro ST_CHECK_NZ 0
    jnz %%good
    jmp st_fail
%%good:
%endmacro
%macro ST_CHECK_EQ 0
    je %%good
    jmp st_fail
%%good:
%endmacro

ST_SEG    equ 0x0800
ST_READ   equ 0x0100
ST_SAVE   equ 0x0200
ST_WRITE  equ 0x0300
ST_CHECK  equ 0x0400

selftest_entry:
    mov si,st_title
    call serial_puts

    ; Console status and output routines. CONST returns 0 or FFh.
    call CONST
    cmp al,0
    je .status_ok
    cmp al,0xff
    jne st_fail
.status_ok:
    mov cl,'!'
    call CONOUT
    mov cl,'L'
    call LISTOUT
    mov cl,'P'
    call PUNCH
    mov si,st_console_ok
    call serial_puts

    call LISTST
    cmp al,0xff
    ST_CHECK_EQ

    ; IOBYTE getters and setters (restore the initial value).
    call GETIOBF
    mov [st_saved_iobyte],al
    mov cl,0x55
    call SETIOBF
    call GETIOBF
    cmp al,0x55
    ST_CHECK_EQ
    mov cl,[st_saved_iobyte]
    call SETIOBF
    mov si,st_io_ok
    call serial_puts

    ; DPH, DPB, CSV and ALV pointers and sizing.
    xor cx,cx
    xor dx,dx
    call SELDSK
    cmp bx,dph0
    ST_CHECK_EQ
    cmp word [bx+8],dirbuf
    ST_CHECK_EQ
    cmp word [bx+10],dpb_2d
    ST_CHECK_EQ
    cmp word [bx+12],csv0
    ST_CHECK_EQ
    cmp word [bx+14],alv0
    ST_CHECK_EQ
    cmp word [dpb_2d],32
    ST_CHECK_EQ
    cmp byte [dpb_2d+2],4
    ST_CHECK_EQ
    cmp byte [dpb_2d+3],15
    ST_CHECK_EQ
    cmp byte [dpb_2d+4],1
    ST_CHECK_EQ
    cmp word [dpb_2d+5],151
    ST_CHECK_EQ
    cmp word [dpb_2d+7],63
    ST_CHECK_EQ
    cmp byte [dpb_2d+9],0x80
    ST_CHECK_EQ
    cmp word [dpb_2d+11],16
    ST_CHECK_EQ
    cmp word [dpb_2d+13],4
    ST_CHECK_EQ
    mov si,st_dph_ok
    call serial_puts

    ; No skew. SETTRK/HOME/SETSEC/SETDMA/SETDMAB state setters.
    mov cx,7
    call SECTRAN
    cmp bx,7
    ST_CHECK_EQ
    mov cx,12
    call SETTRK
    cmp word [cur_track],12
    ST_CHECK_EQ
    call HOME
    cmp word [cur_track],0
    ST_CHECK_EQ
    mov cx,19
    call SETSEC
    cmp word [cur_sector],19
    ST_CHECK_EQ
    mov cx,ST_READ
    call SETDMA
    cmp word [dma_off],ST_READ
    ST_CHECK_EQ
    mov cx,ST_SEG
    call SETDMAB
    cmp word [dma_seg],ST_SEG
    ST_CHECK_EQ
    call GETSEGT
    cmp bx,mrt
    ST_CHECK_EQ
    cmp byte [bx],1
    ST_CHECK_EQ
    cmp word [bx+1],ST_SEG
    ST_CHECK_EQ
    mov si,st_set_ok
    call serial_puts

    ; Check invalid ranges without touching the disk.
    mov cx,80
    call SETTRK
    xor cx,cx
    call SETSEC
    call READ
    cmp al,1
    ST_CHECK_EQ
    mov cx,4
    call SETTRK
    mov cx,32
    call SETSEC
    call READ
    cmp al,1
    ST_CHECK_EQ
    mov si,st_limits_ok
    call serial_puts

    ; READ the real directory first record from C2/H0/S1.
    mov cx,4
    call SETTRK
    xor cx,cx
    call SETSEC
    mov cx,ST_READ
    call SETDMA
    call READ
    or ax,ax
    ST_CHECK_Z
    mov ax,ST_SEG
    mov es,ax
    ; The dedicated self-test image imports ASM86.CMD as its first file.
    ; Checking only the initial known entry is sufficient to prove
    ; the logical record was actually transferred to the caller DMA.
    cmp byte [es:ST_READ],0
    ST_CHECK_EQ
    cmp byte [es:ST_READ+1],'A'
    ST_CHECK_EQ
    cmp byte [es:ST_READ+2],'S'
    ST_CHECK_EQ
    cmp byte [es:ST_READ+3],'M'
    ST_CHECK_EQ
    mov si,st_read_ok
    call serial_puts

    ; Console input test. The IPL has already consumed its attach key.
    mov si,st_key_prompt
    call serial_puts
    call CONIN
    mov [st_key],al
    mov al,[st_key]
    call st_hex_byte
    mov si,st_crlf
    call serial_puts
    mov si,st_key_ok
    call serial_puts

    ; READ/WRITE verification uses the last logical record, on a
    ; disposable copy only. Save the original record in ST_SAVE.
    mov cx,79
    call SETTRK
    mov cx,31
    call SETSEC
    mov cx,ST_SAVE
    call SETDMA
    call READ
    or ax,ax
    ST_CHECK_Z
    push ds
    mov ax,ST_SEG
    mov ds,ax
    mov di,ST_WRITE
    xor bx,bx
    mov cx,128
.fill_pattern:
    mov al,bl
    xor al,0xa6
    mov [di],al
    inc di
    inc bx
    loop .fill_pattern
    pop ds

    mov cx,ST_WRITE
    call SETDMA
    call WRITE
    or ax,ax
    ST_CHECK_Z
    mov byte [st_dirty],1

    mov cx,ST_CHECK
    call SETDMA
    call READ
    or ax,ax
    jnz st_restore_failed
    mov ax,ST_SEG
    mov es,ax
    xor bx,bx
    mov cx,128
.compare:
    mov al,bl
    xor al,0xa6
    cmp [es:bx+ST_CHECK],al
    jne st_restore_failed
    inc bx
    loop .compare

    call st_restore
    or ax,ax
    ST_CHECK_Z
    mov byte [st_dirty],0
    mov si,st_write_ok
    call serial_puts

    mov si,st_pass
    call serial_puts
    jmp st_halt

st_restore_failed:
    mov si,st_write_bad
    call serial_puts
    call st_restore
    or ax,ax
    jnz st_restore_bad
    mov byte [st_dirty],0
    jmp st_fail

st_restore_bad:
    mov si,st_restore_bad_msg
    call serial_puts
    jmp st_halt

st_restore:
    ; Rewrite previously saved 128-byte record to the same track/sector.
    mov cx,79
    call SETTRK
    mov cx,31
    call SETSEC
    mov cx,ST_SAVE
    call SETDMA
    call WRITE
    ret

st_fail:
    mov si,st_fail_msg
    call serial_puts
    cmp byte [st_dirty],0
    je st_halt
    call st_restore
    or ax,ax
    jnz st_restore_bad
    mov byte [st_dirty],0
st_halt:
    cli
.wait:
    hlt
    jmp .wait

; AL -> two uppercase hex digits, serial; preserves AX/BX.
st_hex_byte:
    push ax
    push bx
    mov bl,al
    shr al,1
    shr al,1
    shr al,1
    shr al,1
    call st_hex_nibble
    mov al,bl
    and al,15
    call st_hex_nibble
    pop bx
    pop ax
    ret
st_hex_nibble:
    cmp al,10
    jb .digit
    add al,'A'-10
    jmp serial_putc
.digit:
    add al,'0'
    jmp serial_putc

st_saved_iobyte db 0
st_key db 0
st_dirty db 0
st_title db 13,10,'CBIOS SELFTEST (NO CCP/BDOS)',13,10,0
st_console_ok db 13,10,'PASS CONOUT/LISTOUT/PUNCH/CONST/LISTST',13,10,0
st_io_ok db 'PASS GETIOBF/SETIOBF',13,10,0
st_dph_ok db 'PASS SELDSK/DPH/DPB',13,10,0
st_set_ok db 'PASS SETTRK/HOME/SETSEC/SETDMA/SETDMAB/SECTRAN/GETSEGT',13,10,0
st_limits_ok db 'PASS READ invalid track/record',13,10,0
st_read_ok db 'PASS READ directory ASM86.CMD',13,10,0
st_key_prompt db 'Press one key for CONIN test: ',0
st_key_ok db 13,10,'PASS CONIN',13,10,0
st_write_ok db 'PASS WRITE/READ/RESTORE',13,10,0
st_write_bad db 'FAIL WRITE verify; restoring...',13,10,0
st_restore_bad_msg db 'FAIL RESTORE: disposable disk changed',13,10,0
st_pass db 'PASS CBIOS SELFTEST',13,10,0
st_fail_msg db 'FAIL CBIOS SELFTEST',13,10,0
st_crlf db 13,10,0
