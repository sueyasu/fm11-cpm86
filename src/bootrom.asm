; Diagnostic firmware for the FM-11 8088/V20 card.
; ROM is mapped at FF000h-FFFFFh. Hardware reset fetches FFFF0h.
; Prints to the shared 8251 at FD06/FD07 and halts.
; This is a bring-up ROM, not yet the CP/M-86 disk IPL.
cpu 8086
bits 16
org 0

entry:
    cli
    push cs
    pop ds
    mov si,message
    mov dx,0xFD07
    mov al,0x4E
    out dx,al
    mov al,0x37
    out dx,al
.next:
    lodsb
    or al,al
    jz .halt
    mov ah,al
    mov dx,0xFD07
.wait:
    in al,dx
    test al,0x01
    jz .wait
    mov al,ah
    mov dx,0xFD06
    out dx,al
    jmp .next
.halt:
    hlt
    jmp .halt
message db 'FM-11 8088/V20 CP/M-86 bring-up ROM',13,10,0

times 0xFF0-($-$$) db 0
reset_vector:
    jmp 0xFF00:entry
times 0x1000-($-$$) db 0
