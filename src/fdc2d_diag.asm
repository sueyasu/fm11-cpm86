; FM-11 8088 Mini-FDC read-only diagnostic ROM.
; Read C=0 H=0 S=1 (256 bytes) through 8237 CH0 to physical 0000:2000.
; No disk writes. Works only with a mounted 2D disk on Mini FDC unit 0.
cpu 8086
bits 16
org 0

SER_DATA     equ 0xFD06
SER_STATUS   equ 0xFD07
BUF_OFFSET   equ 0x2000

entry:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x7000
    mov es,ax
    push cs
    pop ds

    mov dx,SER_STATUS
    mov al,0x4E
    out dx,al
    mov al,0x37
    out dx,al

    ; SDL creates its PTY before the guest CPU starts, but does not wait
    ; for a terminal to attach.  Wait for one incoming byte before any
    ; diagnostic output, so the user can connect and press a key.
.wait_serial:
    mov dx,SER_STATUS
    in al,dx
    test al,0x02           ; USART RX ready
    jz .wait_serial
    mov dx,SER_DATA
    in al,dx               ; consume trigger byte
    mov si,msg_start
    call puts

    ; Mask channel 0 before changing the DMA configuration.
    mov dx,0x1A
    mov al,4
    out dx,al
    mov dx,0x1C
    xor al,al
    out dx,al               ; clear 8237 first/last byte flip-flop
    mov dx,0x10
    xor al,al
    out dx,al               ; address low = 00h
    mov al,0x20
    out dx,al               ; address high = 20h
    mov dx,0x11
    mov al,0xFF
    out dx,al               ; count low = FFh
    xor al,al
    out dx,al               ; count high = 00h (256 bytes)
    mov dx,0x20
    out dx,al               ; bank 0, physical DMA address 02000h
    mov dx,0x1B
    mov al,0x44
    out dx,al               ; CH0 single, I/O -> memory
    mov dx,0x18
    in al,dx                ; clear stale terminal-count flag

    mov dx,0xFD19
    xor al,al
    out dx,al               ; cylinder 0
    inc dx
    mov al,1
    out dx,al               ; physical sector 1
    mov dx,0xFD1C
    xor al,al
    out dx,al               ; head 0
    inc dx
    out dx,al               ; drive 0

    mov dx,0x1A
    out dx,al               ; unmask CH0
    mov dx,0xFD18
    mov al,0x80
    out dx,al               ; READ SECTOR
    mov cx,0xFFFF
.poll:
    in al,dx
    test al,0x10
    jnz .failed
    test al,0x02
    jz .complete
    loop .poll
    jmp .failed
.complete:
    or al,al
    jnz .failed
    mov dx,0x18
    in al,dx
    test al,1
    jz .failed

    mov si,msg_ok
    call puts
    ; Dump the first 16 bytes. ROM strings use CS; DMA buffer uses 0000h.
    push ds
    xor ax,ax
    mov ds,ax
    mov si,BUF_OFFSET
    mov cx,16
.dump:
    lodsb
    call hex_byte
    mov al,' '
    call putc
    loop .dump
    pop ds
    mov si,msg_crlf
    call puts
    jmp .halt

.failed:
    mov si,msg_error
    call puts
.halt:
    mov dx,0x1A
    mov al,4
    out dx,al               ; leave CH0 masked
    hlt
    jmp .halt

; AL -> two hexadecimal characters on the serial interface.
hex_byte:
    push ax
    push bx
    mov bl,al
    shr al,1                ; 8086 cannot shift by immediate 4
    shr al,1
    shr al,1
    shr al,1
    call hex_nibble
    mov al,bl
    and al,0x0F
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

puts:
    lodsb
    or al,al
    jz .done
    call putc
    jmp puts
.done:
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
    mov dx,SER_DATA
    mov al,ah
    out dx,al
    pop dx
    pop ax
    ret

msg_start db 'FM-11 2D DMA read C0/H0/S1',13,10,0
msg_ok    db 'PASS: TC=1, data: ',0
msg_error db 'FAIL: FDC status or DMA terminal count',13,10,0
msg_crlf  db 13,10,0

times 0xFF0-($-$$) db 0
reset_vector:
    jmp 0xFF00:entry
times 0x1000-($-$$) db 0
