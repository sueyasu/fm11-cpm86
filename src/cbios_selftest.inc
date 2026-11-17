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

%macro ST_DPH_EQ 3
    cmp %2,%3
    je %%good
    push ax
%if %1 = 7 || %1 = 8 || %1 = 9 || %1 = 12
    xor ax,ax
    mov al,%2
%else
    mov ax,%2
%endif
    mov [cs:st_dph_actual],ax
    mov ax,%3
    mov [cs:st_dph_expected],ax
    pop ax
    mov al,%1
    mov [cs:st_dph_case],al
    jmp st_fail_dph
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
    ST_CHECK_EQ
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
    ST_DPH_EQ 1, bx, dph0
    ST_DPH_EQ 2, word [bx+8], dirbuf
    ST_DPH_EQ 3, word [bx+10], dpb_2d
    ST_DPH_EQ 4, word [bx+12], csv0
    ST_DPH_EQ 5, word [bx+14], alv0
    ST_DPH_EQ 6, word [dpb_2d], 32
    ST_DPH_EQ 7, byte [dpb_2d+2], 4
    ST_DPH_EQ 8, byte [dpb_2d+3], 15
    ST_DPH_EQ 9, byte [dpb_2d+4], 1
    ST_DPH_EQ 10, word [dpb_2d+5], 151
    ST_DPH_EQ 11, word [dpb_2d+7], 63
    ST_DPH_EQ 12, byte [dpb_2d+9], 0x80
    ST_DPH_EQ 13, word [dpb_2d+11], 16
    ST_DPH_EQ 14, word [dpb_2d+13], 4
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
    ; Report actual post-INIT MRT length in paragraphs for testing
    ; different emulator RAM capacities (1800h..F700h).
    mov si,st_mrt_length
    call serial_puts
    mov ax,[bx+3]
    call st_hex_word
    mov si,st_crlf
    call serial_puts
    mov si,st_set_ok
    call serial_puts

    ; Check invalid ranges without touching the disk.
    mov cx,80
    call SETTRK
    xor cx,cx
    call SETSEC
    ; Validate the actual CBIOS state just before dispatch.  If the
    ; saved track is not 80, the error is in SETTRK/SETSEC or DS.
    cmp word [cur_track],80
    je .track_state_ok
    mov si,st_bad_track_state
    mov ax,[cur_track]
    jmp st_fail_ax
.track_state_ok:
    ; READ must return an error without reaching the FDC on track 80.
    mov byte [st_rw_entry],0
    mov word [st_rw_ds],0xffff
    mov byte [st_rw_path],0
    mov word [st_rw_track_bx],0xffff
    mov word [st_rw_track_flags],0xffff
    mov word [st_rw_done_ax],0xffff
    ; Snapshot the actual first bytes of the target in memory, not
    ; merely the assembler label. A wrong load/relocation can otherwise
    ; look like a broken CALL/JAE implementation.
    mov ax,cs
    mov [st_read_cs],ax
    mov ax,READ
    mov [st_read_off],ax
    mov al,[cs:READ]
    mov [st_read_code],al
    mov al,[cs:READ+1]
    mov [st_read_code+1],al
    mov al,[cs:READ+2]
    mov [st_read_code+2],al
    mov al,[cs:READ+3]
    mov [st_read_code+3],al
    mov ax,0x5a5a          ; distinguishes an unexecuted/no-op CALL
    call READ
    cmp ax,1
    je .invalid_track_ok
    ; Print both caller-return AX and the independent observations
    ; captured *inside* READ. This identifies the first divergence.
    push ax
    mov si,st_bad_track
    call serial_puts
    pop ax
    call st_hex_word
    mov si,st_trace_target
    call serial_puts
    mov ax,[st_read_cs]
    call st_hex_word
    mov al,':'
    call serial_putc
    mov ax,[st_read_off]
    call st_hex_word
    mov si,st_trace_code
    call serial_puts
    mov al,[st_read_code]
    call st_hex_byte
    mov al,[st_read_code+1]
    call st_hex_byte
    mov al,[st_read_code+2]
    call st_hex_byte
    mov al,[st_read_code+3]
    call st_hex_byte
    mov si,st_trace_entry
    call serial_puts
    mov al,[st_rw_entry]
    call st_hex_byte
    mov si,st_trace_ds
    call serial_puts
    mov ax,[st_rw_ds]
    call st_hex_word
    mov si,st_trace_bx
    call serial_puts
    mov ax,[st_rw_track_bx]
    call st_hex_word
    mov si,st_trace_flags
    call serial_puts
    mov ax,[st_rw_track_flags]
    call st_hex_word
    mov si,st_trace_path
    call serial_puts
    mov al,[st_rw_path]
    call st_hex_byte
    mov si,st_trace_done
    call serial_puts
    mov ax,[st_rw_done_ax]
    call st_hex_word
    mov si,st_crlf
    call serial_puts
    jmp st_fail
.invalid_track_ok:
    mov cx,4
    call SETTRK
    mov cx,32
    call SETSEC
    call READ
    cmp ax,1
    je .invalid_record_ok
    mov si,st_bad_record
    jmp st_fail_ax
.invalid_record_ok:
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
    mov byte [st_dirty],1  ; failure may occur after a partial disk write
    call WRITE
    or ax,ax
    ST_CHECK_Z

    mov cx,ST_CHECK
    call SETDMA
    call READ
    or ax,ax
    jz .readback_ok
    jmp st_restore_failed
.readback_ok:
    mov ax,ST_SEG
    mov es,ax
    xor bx,bx
    mov cx,128
.compare:
    mov al,bl
    xor al,0xa6
    cmp [es:bx+ST_CHECK],al
    je .compare_ok
    jmp st_restore_failed
.compare_ok:
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

; Report the actual returned status (AX) and the failing condition.
; The original status is printed before any serial routine overwrites AX.
; Report the exact SELDSK/DPH/DPB comparison that failed.
; CS-relative diagnostic state also works if the caller's DS is wrong.
st_fail_dph:
    mov si,st_dph_bad
    call serial_puts
    mov al,[cs:st_dph_case]
    call st_hex_byte
    mov si,st_dph_actual_msg
    call serial_puts
    mov ax,[cs:st_dph_actual]
    call st_hex_word
    mov si,st_dph_expected_msg
    call serial_puts
    mov ax,[cs:st_dph_expected]
    call st_hex_word
    mov si,st_crlf
    call serial_puts
    jmp st_fail

st_fail_ax:
    push ax
    call serial_puts
    pop ax
    call st_hex_word
    mov si,st_crlf
    call serial_puts
    jmp st_fail

st_hex_word:
    push ax
    mov al,ah
    call st_hex_byte
    pop ax
    call st_hex_byte
    ret

st_restore_failed:
    mov si,st_write_bad
    call serial_puts
    call st_restore
    or ax,ax
    jz .restore_success
    jmp st_restore_bad
.restore_success:
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
    jne .need_restore
    jmp st_halt
.need_restore:
    call st_restore
    or ax,ax
    jz .restored
    jmp st_restore_bad
.restored:
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

st_dph_case db 0
st_dph_actual dw 0
st_dph_expected dw 0
st_dph_bad db 'FAIL DPH CHECK #',0
st_dph_actual_msg db ' ACTUAL=',0
st_dph_expected_msg db ' EXPECTED=',0
st_saved_iobyte db 0
st_key db 0
st_dirty db 0
st_rw_entry db 0
st_rw_ds dw 0xffff
st_read_cs dw 0xffff
st_read_off dw 0xffff
st_read_code times 4 db 0xff
; Observation slots used only by the CBIOS_SELFTEST code path.
st_rw_track_bx dw 0xffff
st_rw_track_flags dw 0xffff
st_rw_done_ax dw 0xffff
st_rw_path db 0
st_title db 13,10,'CBIOS SELFTEST (NO CCP/BDOS)',13,10,0
st_console_ok db 13,10,'PASS CONOUT/LISTOUT/PUNCH/CONST/LISTST',13,10,0
st_io_ok db 'PASS GETIOBF/SETIOBF',13,10,0
st_dph_ok db 'PASS SELDSK/DPH/DPB',13,10,0
st_mrt_length db 'MRT TPA paragraphs=',0
st_set_ok db 'PASS SETTRK/HOME/SETSEC/SETDMA/SETDMAB/SECTRAN/GETSEGT',13,10,0
st_limits_ok db 'PASS READ invalid track/record',13,10,0
st_bad_track db 'FAIL READ track=80 returned AX=',0
st_trace_target db ' TARGET=',0
st_trace_code db ' CODE=',0
st_trace_entry db ' ENTRY=',0
st_trace_ds db ' DS=',0
st_trace_bx db ' BX=',0
st_trace_flags db ' FLAGS=',0
st_trace_path db ' PATH=',0
st_trace_done db ' DONE_AX=',0
st_bad_track_state db 'FAIL SETTRK/SETSEC cur_track=',0
st_bad_record db 'FAIL READ record=32 returned AX=',0
st_read_ok db 'PASS READ directory ASM86.CMD',13,10,0
st_key_prompt db 'Press one key for CONIN test: ',0
st_key_ok db 13,10,'PASS CONIN',13,10,0
st_write_ok db 'PASS WRITE/READ/RESTORE',13,10,0
st_write_bad db 'FAIL WRITE verify; restoring...',13,10,0
st_restore_bad_msg db 'FAIL RESTORE: disposable disk changed',13,10,0
st_pass db 'PASS CBIOS SELFTEST',13,10,0
st_fail_msg db 'FAIL CBIOS SELFTEST',13,10,0
st_crlf db 13,10,0
