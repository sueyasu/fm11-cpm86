; FM-11 CP/M-86 CBIOS logical record diagnostic.
; ROM loads the actual 0x1900-byte CBIOS from the dedicated 2D test
; disk into 0000:2500, then calls its real 21-entry jump table.
; The scratch sector is C1/H0/S1 on the generated disposable image.
cpu 8086
bits 16
org 0

SER_DATA    equ 0xFD06
SER_STATUS  equ 0xFD07
BIOS_BASE   equ 0x2500
BIOS_BYTES  equ 0x1900
RECORD0     equ 0x6000
RECORD1     equ 0x6080
WRITEBUF    equ 0x6400
CHECKBUF    equ 0x6600
CHECKHALF   equ 0x6680
DIRTY_FLAG  equ 0x7000
BIOS_GATE   equ 0x7100

; 21 near jump vectors at 0000:2500 (three bytes each).
BIOS_SELDSK equ BIOS_BASE+9*3
BIOS_SETTRK equ BIOS_BASE+10*3
BIOS_SETSEC equ BIOS_BASE+11*3
BIOS_SETDMA equ BIOS_BASE+12*3
BIOS_READ   equ BIOS_BASE+13*3
BIOS_WRITE  equ BIOS_BASE+14*3
BIOS_SETDMAB equ BIOS_BASE+17*3

; 8086 supports only short conditional jumps: take the near JMP on error.
%macro FAIL_Z 0
    jnz %%ok
    jmp test_failed
%%ok:
%endmacro
%macro FAIL_NZ 0
    jz %%ok
    jmp test_failed
%%ok:
%endmacro
%macro FAIL_C 0
    jnc %%ok
    jmp test_failed
%%ok:
%endmacro
%macro FAIL_RESTORE_C 0
    jnc %%ok
    jmp restore_failed
%%ok:
%endmacro

entry:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x9000
    mov ds,ax
    mov es,ax
    mov byte [DIRTY_FLAG],0
    ; Cross-segment near-call gate, using 8086 PUSH/RET rather than
    ; indirect FF-group CALL.  CBIOS returns with a near RET.
    ; 7100: PUSH BP            save BP
    ; 7101: MOV BP,7107h      post-CBIOS continuation
    ; 7104: PUSH BP            near return address
    ; 7105: PUSH BX            CBIOS vector (0000:25xx)
    ; 7106: RET                transfer to CBIOS without FF opcode
    ; 7107: POP BP
    ; 7108: RETF               return to ROM caller
    mov byte [BIOS_GATE],0x55
    mov byte [BIOS_GATE+1],0xBD
    mov word [BIOS_GATE+2],BIOS_GATE+7
    mov byte [BIOS_GATE+4],0x55
    mov byte [BIOS_GATE+5],0x53
    mov byte [BIOS_GATE+6],0xC3
    mov byte [BIOS_GATE+7],0x5D
    mov byte [BIOS_GATE+8],0xCB
    mov dx,SER_STATUS
    mov al,0x4E
    out dx,al
    mov al,0x37
    out dx,al

    ; Connection gate: SDL creates PTY before executing the guest but
    ; doesn't block for a terminal connection.
.wait_key:
    mov dx,SER_STATUS
    in al,dx
    test al,2
    jz .wait_key
    mov dx,SER_DATA
    in al,dx
    mov si,msg_start
    call puts

    ; Dedicated disk layout: C0/H0/S2..16, then C0/H1/S1..10.
    ; 25 sectors * 256 = 0x1900 CBIOS bytes.
    mov bp,BIOS_BASE
    mov si,2                ; 1-based sector
    xor di,di               ; side 0
    mov bx,25
.load:
    mov ax,bp
    mov ch,0
    mov cx,si
    mov dh,0
    or di,di
    jz .side_ready
    mov dh,1
.side_ready:
    call fdc_read
    jnc .loaded_sector
    jmp load_failed
.loaded_sector:
    ; Verify the very first 256-byte DMA transfer before proceeding.
    ; The CBIOS image starts with an E9 near-JMP vector at 0000:2500.
    cmp bp,BIOS_BASE
    jne .next_buffer
    cmp byte [BIOS_BASE],0xE9
    je .first_ok
    mov si,msg_first_bad
    call puts
    mov si,msg_ram_bios
    call puts
    mov si,BIOS_BASE
    mov cx,16
    call hex_dump
    mov si,msg_crlf
    call puts
    mov si,msg_ram_2000
    call puts
    mov si,0x2000
    mov cx,16
    call hex_dump
    mov si,msg_crlf
    call puts
    jmp stop
.first_ok:
    mov si,msg_first_ok
    call puts
.next_buffer:
    add bp,256
    inc si
    cmp si,17
    jb .next
    mov si,1
    inc di
.next:
    dec bx
    jnz .load

    mov si,msg_loaded
    call puts

    ; Report actual loaded bytes, rather than treating successful DMA
    ; terminal count as proof that the correct CBIOS image arrived.
    mov si,msg_vector
    call puts
    mov si,BIOS_SELDSK
    mov cx,3
    call hex_dump
    mov si,msg_target
    call puts
    mov bx,[BIOS_SELDSK+1]
    add bx,BIOS_SELDSK+3
    mov ax,bx
    call hex_word
    mov al,' '
    call putc
    cmp bx,BIOS_BASE
    jb .bad_vector
    cmp bx,BIOS_BASE+BIOS_BYTES-2
    ja .bad_vector
    mov si,bx
    mov cx,2
    call hex_dump
    mov si,msg_crlf
    call puts

    ; Match the two-byte 8086 SELDSK prologue and the jump opcode.
    cmp byte [BIOS_SELDSK],0xE9
    jne .bad_vector
    cmp word [bx],0xDB31
    jne .bad_vector
    mov si,msg_vector_ok
    call puts
    jmp short .vector_ok
.bad_vector:
    jmp invalid_bios
.vector_ok:
    mov si,msg_sel
    call puts

    ; Initialize CP/M disk state without invoking INIT, which jumps to
    ; the as-yet-unloaded CCP/BDOS core.
    xor cx,cx
    xor dx,dx
    mov bx,BIOS_SELDSK
    call bios_call
    or bx,bx
    FAIL_Z
    mov si,msg_sel_ok
    call puts
    mov cx,2                ; track 2 = cylinder 1, side 0
    mov bx,BIOS_SETTRK
    call bios_call
    xor cx,cx               ; DMA segment 0
    mov bx,BIOS_SETDMAB
    call bios_call

    mov si,msg_read_start
    call puts
    ; Read logical record 0 into RECORD0.
    xor cx,cx
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,RECORD0
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_READ
    call bios_call
    or al,al
    FAIL_NZ
    mov si,msg_record0
    call puts
    mov si,RECORD0
    mov ah,0x5A
    call verify_record
    FAIL_C

    ; Read logical record 1; verify the other 128-byte half.
    mov cx,1
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,RECORD1
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_READ
    call bios_call
    or al,al
    FAIL_NZ
    mov si,msg_record1
    call puts
    mov si,RECORD1
    mov ah,0xA5
    call verify_record
    FAIL_C
    mov si,msg_read
    call puts

    ; Generate a temporary record with pattern byte(index) XOR C3h.
    mov si,WRITEBUF
    xor bx,bx
    mov cx,128
.fill:
    mov al,bl
    xor al,0xC3
    mov [si],al
    inc si
    inc bx
    loop .fill

    mov si,msg_write_start
    call puts
    ; Mark scratch as possibly modified before issuing WRITE. Always
    ; attempt to restore the original first half after this point.
    mov byte [DIRTY_FLAG],1
    xor cx,cx
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,WRITEBUF
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_WRITE
    call bios_call
    or al,al
    FAIL_NZ

    ; Read record 0 back into a separate location and compare.
    xor cx,cx
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,CHECKBUF
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_READ
    call bios_call
    or al,al
    FAIL_NZ
    mov si,CHECKBUF
    mov ah,0xC3
    call verify_record
    FAIL_C

    ; Verify READ/MODIFY/WRITE preserved the other half of the sector.
    mov cx,1
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,CHECKHALF
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_READ
    call bios_call
    or al,al
    FAIL_NZ
    mov si,CHECKHALF
    mov ah,0xA5
    call verify_record
    FAIL_C

    call restore_sector
    FAIL_RESTORE_C
    mov byte [DIRTY_FLAG],0
    mov si,msg_pass
    call puts
    jmp stop

load_failed:
    mov si,msg_load_fail
    call puts
    jmp stop
invalid_bios:
    mov si,msg_invalid_bios
    call puts
    jmp stop
test_failed:
    mov si,msg_test_fail
    call puts
    cmp byte [DIRTY_FLAG],0
    je stop
    call restore_sector
    FAIL_RESTORE_C
    mov si,msg_restored
    call puts
    jmp stop
restore_failed:
    mov si,msg_restore_fail
    call puts
stop:
    hlt
    jmp stop

; Invoke BX=CBIOS vector via RAM gate in segment 0000h.
; Gate uses PUSH BP / MOV BP,continuation / PUSH BP / PUSH BX / RET,
; then POP BP / RETF. It does not modify AX or the BIOS return value.
bios_call:
    mov ax,cs
    push ax                 ; far return CS = ROM segment FF00h
    mov ax,.returned
    push ax                 ; far return IP in ROM
    xor ax,ax
    push ax                 ; target CS = 0000h
    mov ax,BIOS_GATE
    push ax                 ; target IP = gate
    retf
.returned:
    ret

; Write the saved original record 0 back to the scratch sector.
; CF and AL are returned from the CBIOS WRITE operation.
restore_sector:
    xor cx,cx
    mov bx,BIOS_SETSEC
    call bios_call
    mov cx,RECORD0
    mov bx,BIOS_SETDMA
    call bios_call
    mov bx,BIOS_WRITE
    call bios_call
    or al,al
    jnz .bad
    clc
    ret
.bad:
    stc
    ret

; DS:SI = 128-byte record, AH = expected XOR pattern.
; Each byte must equal its zero-based index XOR AH.
verify_record:
    xor bx,bx
    mov cx,128
.loop:
    mov al,bl
    xor al,ah
    cmp [si],al
    jne .bad
    inc si
    inc bx
    loop .loop
    clc
    ret
.bad:
    stc
    ret

; AX=physical offset (bank 0), CH=cylinder, CL=sector, DH=head.
; Sector read uses 8237 CH0; preserves AX/BX/CX/DX/SI/DI/BP.
; Returns CF=0 only if FDC completed and DMA terminal count asserted.
fdc_read:
    push ax
    push bx
    push cx
    push dx
    push si
    mov bl,dh               ; save requested head before reusing DX for ports
    mov si,ax
    mov dx,0x1A
    mov al,4
    out dx,al               ; mask channel 0
    mov dx,0x1C
    xor al,al
    out dx,al               ; reset 8237 byte flip-flop
    mov dx,0x10
    mov ax,si
    out dx,al
    mov al,ah
    out dx,al               ; DMA address
    mov dx,0x11
    mov al,0xFF
    out dx,al
    xor al,al
    out dx,al               ; DMA count = 255
    mov dx,0x20
    out dx,al               ; DMA bank = 0
    mov dx,0x1B
    mov al,0x44
    out dx,al               ; single, device -> memory
    mov dx,0x18
    in al,dx                ; clear prior TC
    mov dx,0xFD19
    mov al,ch
    out dx,al
    inc dx
    mov al,cl
    out dx,al
    mov dx,0xFD1C
    mov al,bl               ; original head, NOT DH of port address FD1Ch
    out dx,al
    inc dx
    xor al,al
    out dx,al               ; Mini FDC drive 0
    mov dx,0x1A
    out dx,al               ; unmask DMA channel 0
    mov dx,0xFD18
    mov al,0x80
    out dx,al               ; read sector
    mov cx,0xFFFF
.poll:
    in al,dx
    test al,0x10
    jnz .error
    test al,2
    jz .complete
    loop .poll
    jmp .error
.complete:
    or al,al
    jnz .error
    mov dx,0x18
    in al,dx
    test al,1
    jz .error
    clc
    jmp .finish
.error:
    stc
.finish:
    pushf
    mov dx,0x1A
    mov al,4
    out dx,al
    popf
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; Print a hex byte from AL, preserving the other general registers.
hex_byte:
    push ax
    push bx
    mov bl,al
    shr al,1
    shr al,1
    shr al,1
    shr al,1
    call hex_nibble
    mov al,bl
    and al,15
    call hex_nibble
    pop bx
    pop ax
    ret
hex_nibble:
    cmp al,10
    jb .digit
    add al,'A'-10
    jmp putc
.digit:
    add al,'0'
    jmp putc

; AX = word to print, high byte first.
hex_word:
    push ax
    mov al,ah
    call hex_byte
    pop ax
    call hex_byte
    ret

; DS:SI points to CX bytes.
hex_dump:
    push ax
    push cx
    push si
.next:
    lodsb
    call hex_byte
    mov al,' '
    call putc
    loop .next
    pop si
    pop cx
    pop ax
    ret

; ROM strings are located in CS, while the BIOS requires DS=0000h.
puts:
    push ds
    push si
    push cs
    pop ds
.next:
    lodsb
    or al,al
    jz .done
    call putc
    jmp .next
.done:
    pop si
    pop ds
    ret
putc:
    push ax
    push dx
    mov ah,al
    mov dx,SER_STATUS
.wait:
    in al,dx
    test al,1
    jz .wait
    mov al,ah
    mov dx,SER_DATA
    out dx,al
    pop dx
    pop ax
    ret

msg_start       db 'CBIOS 128-byte record test',13,10,0
msg_first_ok    db 'PASS: first CBIOS DMA sector',13,10,0
msg_first_bad   db 'FAIL: first CBIOS DMA sector has no E9 vector',13,10,0
msg_ram_bios    db 'RAM 2500: ',0
msg_ram_2000    db 'RAM 2000: ',0
msg_sel         db 'STEP: SELDSK',13,10,0
msg_vector      db 'SELDSK vector: ',0
msg_target      db 13,10,'Target: ',0
msg_crlf        db 13,10,0
msg_vector_ok   db 'PASS: SELDSK vector and target bytes',13,10,0
msg_invalid_bios db 'FAIL: CBIOS SELDSK vector/target content',13,10,0
msg_sel_ok      db 'STEP: SELDSK OK',13,10,0
msg_read_start  db 'STEP: READ record 0',13,10,0
msg_record0     db 'STEP: READ record 0 returned',13,10,0
msg_record1     db 'STEP: READ record 1 returned',13,10,0
msg_write_start db 'STEP: WRITE record 0',13,10,0
msg_loaded      db 'CBIOS DMA transfers completed (checking image)',13,10,0
msg_read        db 'PASS: records 0 and 1 read',13,10,0
msg_pass        db 'PASS: WRITE, RMW, verify, restore',13,10,0
msg_load_fail   db 'FAIL: CBIOS disk load',13,10,0
msg_test_fail   db 'FAIL: CBIOS READ/WRITE or data',13,10,0
msg_restored    db 'Original record restored',13,10,0
msg_restore_fail db 'FAIL: original record restore',13,10,0

times 0xFF0-($-$$) db 0
reset_vector:
    jmp 0xFF00:entry
times 0x1000-($-$$) db 0
