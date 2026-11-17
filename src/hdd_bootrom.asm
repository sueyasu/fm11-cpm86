; FM-11 8088 reset ROM HDD bootstrap (4 KiB at FF000h).
; Reads sector LBA0-1 with MDC DMA2 into 07C0:0000, then runs IPL.
; Built for the emulator --8088-rom option. The original Fujitsu ROM
; HDD boot route is not modified by this project.
%ifndef CONSOLE_LOCAL
%define CONSOLE_LOCAL 1
%endif
cpu 8086
bits 16
org 0

entry:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x9000
    ; Same PIC setup as the already-working FDD CP/M-86 reset ROM.
    mov al,0x1b
    out 0x00,al
    mov al,0x08
    out 0x01,al
    mov al,0x09
    out 0x01,al
    mov al,0xff
    out 0x01,al
    ; Optional serial attach gate; local console must boot without PTY.
%if CONSOLE_LOCAL = 0
    mov dx,0xfd07
    mov al,0x4e
    out dx,al
    mov al,0x37
    out dx,al
.wait_input:
    in al,dx
    test al,2
    jz .wait_input
    mov dx,0xfd06
    in al,dx
%endif

    call hdd_set_binary
    jc fail
    mov bx,0x7c00
    xor si,si               ; LBA 0
    call hdd_read_sector
    jc fail
    mov bx,0x7d00
    mov si,1                ; LBA 1
    call hdd_read_sector
    jc fail
    xor ax,ax
    mov ds,ax
    cmp byte [0x7c00],0xfa ; first instruction CLI in HDD IPL
    jne fail
    jmp 0x07c0:0

fail:
    cli
.loop:
    hlt
    jmp .loop

%include "src/hdd_boot_io.inc"
times 0xff0-($-$$) db 0
reset_vector:
    jmp 0xff00:entry
times 0x1000-($-$$) db 0
