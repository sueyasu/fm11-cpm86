; Standalone diagnostic resident image. The existing IPL loads exactly
; 0x2500 bytes of (test) core followed by 0x1900 bytes of the real CBIOS.
; The ordinary CP/M-86 CCP/BDOS binaries are not executed.
cpu 8086
bits 16
org 0
    jmp selftest_entry

%include "src/cbios_selftest.inc"
times 0x2500-($-$$) db 0

%define CBIOS_EMBEDDED 1
%define CBIOS_SELFTEST 1
%include "src/cbios.asm"
