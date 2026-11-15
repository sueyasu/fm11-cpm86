; FM-11 EX 8088 disk IPL (2D), 512-byte ROM-loaded bootstrap.
; Expected by this experimental image: ROM reads C0/H0/S1-S2 to
; physical 0000:0400 and transfers execution to 0000:0400.
; The 0x3E00-byte resident follows in C0/H0/S3 onward, 62 sectors.
; The current 4-KiB IPL ROM is NOT copied onto the floppy; this is a
; distinct, compact disk bootstrap.
cpu 8086
bits 16
org 0x0400

FDC_CMD     equ 0xFD18
FDC_TRACK   equ 0xFD19
FDC_SECTOR  equ 0xFD1A
FDC_SIDE    equ 0xFD1C
FDC_DRIVE   equ 0xFD1D
DMA_ADDR    equ 0x10
DMA_COUNT   equ 0x11
DMA_MASK    equ 0x1A
DMA_MODE    equ 0x1B
DMA_FF      equ 0x1C
DMA_TC      equ 0x18
DMA_BANK    equ 0x20

RES_SEG     equ 0x0400
RES_OFF     equ 0x2500
RES_START   equ 0x4000
RES_END     equ 0x7E00

start:
    jmp short boot
    times 13 db 0                  ; reserved bootstrap header space

boot:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x9000
    mov ds,ax
    cld
    mov bx,RES_START               ; physical DMA destination
    xor bp,bp                      ; cylinder
    xor di,di                      ; head
    mov si,3                       ; 1-based sector, after 512-byte IPL
.next:
    mov cx,si
    mov ax,bp
    mov ch,al
    mov dx,di
    mov dh,dl
    call read_256
    jc fail
    add bx,256
    cmp bx,RES_END
    je loaded
    inc si
    cmp si,17
    jb .next
    mov si,1
    inc di
    cmp di,2
    jb .next
    xor di,di
    inc bp
    jmp .next

loaded:
    mov ax,RES_SEG
    mov es,ax
    cmp byte [es:RES_OFF],0xE9     ; real CBIOS vector opcode
    jne fail
    jmp RES_SEG:RES_OFF

fail:
    cli
.halt:
    hlt
    jmp .halt

; Entry: BX = bank-0 DMA physical address; CH = cylinder;
; CL = physical sector 1..16; DH = side. Return CF=0 on success.
; Preserves caller registers, so BX/BP/DI/SI survive the read.
read_256:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si,dx                     ; preserve head in SI high byte
    mov dx,DMA_MASK
    mov al,4
    out dx,al
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
    out dx,al                     ; DMA bank 0, physical < 0x10000
    mov dx,DMA_MODE
    mov al,0x44                  ; CH0, single, I/O -> memory
    out dx,al
    mov dx,DMA_TC
    in al,dx                     ; clear previous TC
    mov dx,FDC_TRACK
    mov al,ch
    out dx,al
    inc dx                       ; sector
    mov al,cl
    out dx,al
    mov dx,FDC_SIDE
    mov ax,si
    mov al,ah
    out dx,al
    inc dx                       ; drive 0
    xor al,al
    out dx,al
    mov dx,DMA_MASK
    out dx,al                     ; unmask DMA CH0
    mov dx,FDC_CMD
    mov al,0x80                  ; physical READ SECTOR
    out dx,al
    mov cx,0xFFFF
.poll:
    in al,dx
    test al,0x10
    jnz .bad
    test al,0x02
    jz .completed
    loop .poll
    jmp .bad
.completed:
    or al,al
    jnz .bad
    mov dx,DMA_TC
    in al,dx
    test al,1
    jz .bad
    clc
    jmp .finish
.bad:
    stc
.finish:
    pushf
    mov dx,DMA_MASK
    mov al,4
    out dx,al                     ; mask channel after transfer
    popf
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

times 0x200-($-$$) db 0
