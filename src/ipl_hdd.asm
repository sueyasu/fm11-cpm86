; FM-11 CP/M-86 HDD disk IPL (512 bytes at physical LBA0-1).
; 8088 reset ROM reads IPL into 07C0:0000; IPL relocates to 0100:0000,
; then loads 62 resident 256-byte records from LBA2..63 at 0400:0000.
; The first HDD cylinder is reserved; CP/M I: begins at cylinder 1.
cpu 8086
bits 16
org 0

start:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x9000
    push cs
    pop ds
    mov ax,0x0100
    mov es,ax
    xor si,si
    xor di,di
    mov cx,256
    cld
    rep movsw
    jmp 0x0100:relocated

relocated:
    push cs
    pop ds
    call hdd_set_binary
    jc halt
    mov bx,0x4000           ; DMA2 physical load destination
    mov si,2                ; skip 512-byte disk IPL
.load:
    call hdd_read_sector
    jc halt
    add bx,256
    inc si
    cmp si,64               ; 62 sectors LBA2..63
    jb .load
    mov ax,0x0400
    mov es,ax
    cmp byte [es:0x2500],0xe9
    jne halt
    jmp 0x0400:0x2500

halt:
    cli
.wait:
    hlt
    jmp .wait

%include "src/hdd_boot_io.inc"
times 512-($-$$) db 0
