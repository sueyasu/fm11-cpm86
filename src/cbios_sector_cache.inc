; One-physical-sector (256-byte) write-through deblocking cache.
; All entry points run DS=CS. fdc2d_buffer is both the DMA bounce
; buffer and the cached sector. No dirty state: every WRITE goes to disk.
;
; Keys: CP/M physical drive (0..8), logical side/head-track, 0-based
; physical sector index. Do not confuse the last item with FDC's 1-based
; sector field. The key is published only after a complete READ.
; NOTE: device access outside this CBIOS (e.g. FORMAT) must invalidate.
;
; Cache replacement is immediate, never deferred. No flush API required.
cache_invalidate:
    mov byte [cache_valid],0
    ret

; Returns CF clear iff fdc2d_buffer contains the requested physical
; 256-byte sector. Key hit does not touch the FDC/HDD.
; Preserves all general registers, DS and ES; CF carries I/O result.
cache_ensure:
    push ax
    push bx
    push cx
    push dx
    mov bx,[cur_sector]
    shr bx,1
    cmp byte [cache_valid],1
    jne .miss
    mov al,[cur_disk]
    cmp al,[cache_drive]
    jne .miss
    mov ax,[cur_track]
    cmp ax,[cache_track]
    jne .miss
    cmp bx,[cache_sector]
    jne .miss
    clc
    jmp .done
.miss:
    ; Once a different sector is requested the old buffer is no longer
    ; trustworthy; physical READ may modify it before returning error.
    mov byte [cache_valid],0
    call sector_physical_read
    jc .done
    mov al,[cur_disk]
    mov [cache_drive],al
    mov ax,[cur_track]
    mov [cache_track],ax
    mov bx,[cur_sector]
    shr bx,1
    mov [cache_sector],bx
    mov byte [cache_valid],1
    clc
.done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; READ and WRITE transport for a *physical* 256-byte sector.
; The logical 128-byte offset is handled only by READ/WRITE above.
; Preserve BX/CX/DX used by the caller; CF is physical I/O result.
sector_physical_read:
    push ax
    push bx
    push cx
    push dx
    mov al,[cur_disk]
    cmp al,8
    je .hdd
    call sector_floppy_chs
    call fdc2d_read
    jmp .done
.hdd:
    call hdd_read
.done:
%ifdef CBIOS_SELFTEST
    inc word [cache_phys_reads]
%endif
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sector_physical_write:
    push ax
    push bx
    push cx
    push dx
    mov al,[cur_disk]
    cmp al,8
    je .hdd
    call sector_floppy_chs
    call fdc2d_write
    jmp .done
.hdd:
    call hdd_write
.done:
%ifdef CBIOS_SELFTEST
    inc word [cache_phys_writes]
%endif
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; For FDD only: current 0-based CP/M logical side-track and logical
; record -> 1-based FDC CHS. These values are consumed by fdc2d_*.
; AL remains the physical CP/M drive number; BX is scratch.
sector_floppy_chs:
    mov bx,[cur_track]
    mov dx,bx
    and dl,1
    mov dh,dl
    shr bx,1
    mov ch,bl
    mov bx,[cur_sector]
    mov cl,bl
    shr cl,1
    inc cl
    ret

cache_valid db 0
cache_drive db 0xff
cache_track dw 0xffff
cache_sector dw 0xffff
%ifdef CBIOS_SELFTEST
cache_phys_reads dw 0
cache_phys_writes dw 0
%endif
