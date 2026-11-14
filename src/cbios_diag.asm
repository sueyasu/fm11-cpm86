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

    ; Initialize CP/M disk state without invoking INIT, which jumps to
    ; the as-yet-unloaded CCP/BDOS core.
    xor cx,cx
    xor dx,dx
    call 0x0000:BIOS_SELDSK
    or bx,bx
    FAIL_Z
    mov cx,2                ; track 2 = cylinder 1, side 0
    call 0x0000:BIOS_SETTRK
    xor cx,cx               ; DMA segment 0
    call 0x0000:BIOS_SETDMAB

    ; Read logical record 0 into RECORD0.
    xor cx,cx
    call 0x0000:BIOS_SETSEC
    mov cx,RECORD0
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_READ
    or al,al
    FAIL_NZ
    mov si,RECORD0
    mov ah,0x5A
    call verify_record
    FAIL_C

    ; Read logical record 1; verify the other 128-byte half.
    mov cx,1
    call 0x0000:BIOS_SETSEC
    mov cx,RECORD1
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_READ
    or al,al
    FAIL_NZ
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

    ; Mark scratch as possibly modified before issuing WRITE. Always
    ; attempt to restore the original first half after this point.
    mov byte [DIRTY_FLAG],1
    xor cx,cx
    call 0x0000:BIOS_SETSEC
    mov cx,WRITEBUF
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_WRITE
    or al,al
    FAIL_NZ

    ; Read record 0 back into a separate location and compare.
    xor cx,cx
    call 0x0000:BIOS_SETSEC
    mov cx,CHECKBUF
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_READ
    or al,al
    FAIL_NZ
    mov si,CHECKBUF
    mov ah,0xC3
    call verify_record
    FAIL_C

    ; Verify READ/MODIFY/WRITE preserved the other half of the sector.
    mov cx,1
    call 0x0000:BIOS_SETSEC
    mov cx,CHECKHALF
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_READ
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

; Write the saved original record 0 back to the scratch sector.
; CF and AL are returned from the CBIOS WRITE operation.
restore_sector:
    xor cx,cx
    call 0x0000:BIOS_SETSEC
    mov cx,RECORD0
    call 0x0000:BIOS_SETDMA
    call 0x0000:BIOS_WRITE
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
    mov al,dh
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
msg_loaded      db 'CBIOS loaded from 2D disk',13,10,0
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
