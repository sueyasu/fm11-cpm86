; FM-11 8088 Mini-FDC CP/M-86 disk loader ROM (bring-up).
; Dedicated raw 2D media, C0/H0/S1 onward, 62 x 256-byte sectors.
; Resident image = 0x2500-byte external core + 0x1900-byte FM-11 CBIOS.
; Loaded at 0800:0000, BIOS INIT entry at 0800:2500.
; First stage waits for one serial byte so SDL PTY users can attach.
cpu 8086
bits 16
org 0

SER_DATA    equ 0xFD06
SER_STATUS  equ 0xFD07
RES_SEG     equ 0x0800
RES_PHYS    equ 0x8000
RES_SECTORS equ 62
BIOS_ENTRY  equ 0x2500

entry:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x7000
    push cs
    pop ds
    mov dx,SER_STATUS
    mov al,0x4E
    out dx,al
    mov al,0x37
    out dx,al

    ; PTY connection gate for early bring-up. No output is emitted before
    ; a user has attached to the PTY and sent one character.
.wait_key:
    mov dx,SER_STATUS
    in al,dx
    test al,2
    jz .wait_key
    mov dx,SER_DATA
    in al,dx
    mov si,msg_start
    call puts

    mov bx,RES_PHYS         ; 8237 channel 0 physical DMA destination
    mov word [remaining],RES_SECTORS
    xor bp,bp               ; cylinder
    xor di,di               ; side
    mov si,1                ; sector, 1-based
.load:
    ; Read one physical 256-byte sector into low memory.  BIOS itself is
    ; assembled with ORG 2500h and will execute from segment 0800h.
    mov cx,si               ; CL = sector
    mov ax,bp
    mov ch,al               ; CH = cylinder
    mov dx,di
    mov dh,dl               ; DH = side
    mov ax,bx
    call fdc_read
    jc load_failed
    add bx,256
    inc si
    cmp si,17
    jb .next
    mov si,1
    inc di
    cmp di,2
    jb .next
    xor di,di
    inc bp
.next:
    dec word [remaining]
    jnz .load

    ; Validate the resident CBIOS first vector, not just the DMA TC bit.
    mov ax,RES_SEG
    mov es,ax
    cmp byte [es:BIOS_ENTRY],0xE9
    jne invalid_bios
    mov si,msg_loaded
    call puts
    ; INIT builds BIOS data/stack/interrupt bindings and jumps to CCP.
    jmp RES_SEG:BIOS_ENTRY

load_failed:
    mov si,msg_read_fail
    call puts
    jmp halt
invalid_bios:
    mov si,msg_invalid
    call puts
halt:
    hlt
    jmp halt

; AX = 20-bit physical DMA address low 16 bits, CH=cyl, CL=sector, DH=side.
; These images load below 0x10000 so the 8237 bank is always zero.
; Preserves all general registers. CF=0 iff full physical sector completed.
fdc_read:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    mov bp,dx               ; preserve DH before DX is reused as port number
    mov si,ax
    mov dx,0x1A
    mov al,4
    out dx,al               ; mask channel 0
    mov dx,0x1C
    xor al,al
    out dx,al               ; reset flip-flop
    mov dx,0x10
    mov ax,si
    out dx,al
    mov al,ah
    out dx,al               ; DMA address low and high
    mov dx,0x11
    mov al,0xFF
    out dx,al
    xor al,al
    out dx,al               ; count=0x00FF
    mov dx,0x20
    out dx,al               ; bank 0
    mov dx,0x1B
    mov al,0x44
    out dx,al               ; single transfer, I/O->memory, channel 0
    mov dx,0x18
    in al,dx                ; clear previous TC
    mov dx,0xFD19
    mov al,ch
    out dx,al               ; cylinder
    inc dx
    mov al,cl
    out dx,al               ; sector
    mov dx,0xFD1C
    mov ax,bp
    mov al,ah
    out dx,al               ; saved head (not port number's DH!)
    inc dx
    xor al,al
    out dx,al               ; physical drive 0
    mov dx,0x1A
    out dx,al               ; unmask channel 0
    mov dx,0xFD18
    mov al,0x80
    out dx,al               ; Mini-FDC READ
    mov cx,0xFFFF
.poll:
    in al,dx
    test al,0x10
    jnz .fail
    test al,0x02
    jz .done
    loop .poll
    jmp .fail
.done:
    or al,al
    jnz .fail
    mov dx,0x18
    in al,dx
    test al,1
    jz .fail
    clc
    jmp .finish
.fail:
    stc
.finish:
    pushf
    mov dx,0x1A
    mov al,4
    out dx,al
    popf
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

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
    mov al,ah
    mov dx,SER_DATA
    out dx,al
    pop dx
    pop ax
    ret

remaining dw 0
msg_start db 'FM-11 CP/M-86 2D IPL: loading resident',13,10,0
msg_loaded db 'FM-11 CP/M-86 IPL: CBIOS vector OK, entering INIT',13,10,0
msg_read_fail db 'FAIL: resident sector read / DMA',13,10,0
msg_invalid db 'FAIL: resident CBIOS image is invalid',13,10,0

times 0xFF0-($-$$) db 0
reset_vector:
    jmp 0xFF00:entry
times 0x1000-($-$$) db 0
