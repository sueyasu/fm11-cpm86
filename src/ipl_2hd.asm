; FM-11 8088 2HD disk IPL, boot ROM entry 07C0:0000.
; Fits four 128-byte FM boot sectors on C0/H0. The first action is relocation
; from physical 07C00h to 01000h, because the 0x3E00-byte resident
; image loaded at 04000h..07DFFh would overwrite the running IPL.
; Serial diagnostics: I=entry, R=relocated, .=sector, E=read error,
; V=CBIOS vector mismatch, J=jump to CBIOS.
cpu 8086
bits 16
org 0

SER_STATUS equ 0xFD07
SER_DATA   equ 0xFD06
DMA_ADDR   equ 0x12
DMA_COUNT  equ 0x13
DMA_TC     equ 0x18
DMA_MASK   equ 0x1A
DMA_MODE   equ 0x1B
DMA_FF     equ 0x1C
DMA_BANK   equ 0x21
FDC_CMD    equ 0xFD30
FDC_TRACK  equ 0xFD31
FDC_SIDE   equ 0xFD34

start:
    jmp short relocate
    times 13 db 0

relocate:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x9000             ; establish stack BEFORE calling putc
    push cs
    pop ds
    mov dx,SER_STATUS
    ; The original FM-11 boot ROM can leave USART0 initialized with
    ; DTR asserted and a named-pipe terminal connected. Resetting its
    ; 8251 then drives DTR low and CNamedPipe::DoClose() disconnects it.
    ; Reuse an already-enabled transmitter without touching command port.
    in al,dx
    test al,1                  ; TxRDY
    jnz .serial_ready
    ; On a cold, disabled USART use the proven 8251 reset sequence.
    ; No active transmitter is available in that case.
    xor al,al
    out dx,al
    out dx,al
    out dx,al
    mov al,0x40
    out dx,al
    mov al,0x4E
    out dx,al
    mov al,0x37               ; DTR and TxEN asserted
    out dx,al
.serial_ready:
    mov al,'I'
    call putc
    mov ax,0x0100
    mov es,ax
    xor si,si
    xor di,di
    mov cx,256
    cld
    rep movsw
    jmp 0x0100:boot

boot:
    xor ax,ax
    mov ds,ax
    mov al,'R'
    call putc
    mov bx,0x4000             ; 8237 CH1 physical DMA destination
    xor bp,bp                 ; cylinder
    mov di,1                  ; C0/H1: first 256-byte resident sector
    mov si,1                  ; C0/H0 contains 128-byte FM IPL sectors
.loop:
    call read256
    jnc .read_ok
    mov al,'E'
    call putc
    jmp halt
.read_ok:
    mov al,'.'
    call putc
    add bx,256
    cmp bx,0x7E00             ; 62 sectors, 04000h..07DFFh
    je loaded
    inc si
    cmp si,27
    jb .loop
    mov si,1
    inc di
    cmp di,2
    jb .loop
    xor di,di
    inc bp
    jmp .loop

loaded:
    mov ax,0x0400
    mov es,ax
    cmp byte [es:0x2500],0xE9
    je .valid
    mov al,'V'
    call putc
    jmp halt
.valid:
    mov al,'J'
    call putc
    jmp 0x0400:0x2500

halt:
    cli
.again:
    hlt
    jmp .again

; Serial output does not disturb the load loop's registers.
putc:
    push ax
    push cx
    push dx
    mov ah,al
    mov dx,SER_STATUS
    mov cx,0xFFFF              ; no indefinite loop if TXRDY stays low
.wait:
    in al,dx
    test al,1
    jnz .ready
    loop .wait
    jmp .done                  ; no serial connection or USART failure
.ready:
    mov dx,SER_DATA
    mov al,ah
    out dx,al
.done:
    pop dx
    pop cx
    pop ax
    ret

; BX=DMA destination (bank 0); BP=cylinder; DI=head; SI=sector.
; Preserves BX/BP/DI/SI, clobbers AX/CX/DX.
; Return CF=0 only when FDC succeeded and DMA terminal count asserted.
read256:
    mov dx,DMA_MASK
    mov al,5                 ; mask channel 1
    out dx,al
    call position_head
    jnc .positioned
    ret                       ; DMA remains masked on positioning error
.positioned:
    mov dx,DMA_FF
    xor al,al
    out dx,al
    mov dx,DMA_ADDR
    mov ax,bx
    out dx,al
    mov al,ah
    out dx,al
    mov dx,DMA_COUNT
    mov al,0xFF
    out dx,al
    xor al,al
    out dx,al
    mov dx,DMA_BANK
    out dx,al
    mov dx,DMA_MODE
    mov al,0x45              ; channel 1, I/O to RAM
    out dx,al
    mov dx,DMA_TC
    in al,dx
    mov dx,FDC_TRACK+1        ; sector register
    mov ax,si
    out dx,al                 ; sector
    mov dx,FDC_SIDE
    mov ax,di
    out dx,al                 ; head
    mov dx,DMA_MASK
    mov al,1
    out dx,al                 ; unmask DMA CH1
    mov dx,FDC_CMD
    mov al,0x80
    out dx,al                 ; FDC READ
    mov cx,0xFFFF
.poll:
    in al,dx
    test al,0x10
    jnz .bad
    test al,3                 ; BUSY or DRQ
    jz .complete
    loop .poll
    jmp .bad
.complete:
    or al,al
    jnz .bad
    mov dx,DMA_TC
    in al,dx
    test al,2                ; DMA channel 1 terminal count
    jz .bad
    clc
    jmp .finish
.bad:
    stc
.finish:
    pushf
    mov dx,DMA_MASK
    mov al,5                 ; mask channel 1 on exit
    out dx,al
    popf
    ret

; The boot ROM loads four 128-byte FM sectors as a 512-byte first-stage image.
position_head:
    ; Drive 0 is the boot unit. The relocated IPL owns its position byte.
    mov dx,FDC_SIDE+1
    xor al,al
    out dx,al
    mov dx,FDC_CMD
    call wait_type1_idle
    jc .done
    cmp byte [cs:physical_cyl],0xff
    jne .known
    mov al,0x0b               ; RESTORE without verify
    call type1
    jc .done
    mov byte [cs:physical_cyl],0
.known:
    mov ax,bp
    cmp al,[cs:physical_cyl]
    je .ok
    mov dx,FDC_TRACK+2        ; DATA = destination cylinder
    out dx,al
    mov dx,FDC_CMD
    mov al,0x1b               ; SEEK without verify
    call type1
    jc .done
    mov ax,bp
    mov [cs:physical_cyl],al
.ok:
    clc
.done:
    ret

type1:
    out dx,al
    mov cx,16
.delay:
    loop .delay
    call wait_type1_idle
    jc .done
    test al,0x90              ; not ready / seek error
    jz .done
    stc
.done:
    ret

wait_type1_idle:
    mov cx,0xffff
.poll:
    in al,dx
    test al,1                 ; Type I bit 1 is INDEX, not DRQ
    jz .done
    loop .poll
    stc
.done:
    ret

physical_cyl db 0xff

times 0x200-($-$) db 0
