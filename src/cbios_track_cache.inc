; FM-11 CP/M-86 track cache: two 8 KiB windows in reserved upper RAM.
; Each window stores one physical side/head-track (up to 32 x 256).
; Lazy sector fill; valid/dirty 32-bit masks per window; write-back.
; DS=CS on entry; fdc2d_buffer remains the only hardware DMA buffer.
;
; The two windows are removed from the TOP of the MRT TPA during INIT,
; leaving >=80 KiB TPA on a 128 KiB machine. Only the resident
; metadata is in the fixed 1900h BIOS image.
cache_init:
    mov ax,[mrt_tpa_len]
    sub ax,0x0400               ; reserve 16 KiB = 0400h paragraphs
    mov [mrt_tpa_len],ax
    add ax,0x0800               ; MRT start segment
    mov [cache_segments],ax
    add ax,0x0200               ; second 8 KiB window
    mov [cache_segments+2],ax
    mov byte [cache_used],0
    mov byte [cache_next],0
    mov word [cache_valid],0
    mov word [cache_valid+2],0
    mov word [cache_valid+4],0
    mov word [cache_valid+6],0
    mov word [cache_dirty],0
    mov word [cache_dirty+2],0
    mov word [cache_dirty+4],0
    mov word [cache_dirty+6],0
    ret

; Cache-wide invalidate is only safe once all dirty data was flushed.
cache_invalidate:
    mov byte [cache_used],0
    ret

; Map SI=window (0/1), BX=physical sector (0..31) to
; DI=bitmap word offset (0,2,4,6), AX=single bit mask.
; Changes AX/CX/DI, preserves BX and SI.
cache_bit:
    mov di,si
    shl di,1
    shl di,1
    mov ax,bx
    cmp ax,16
    jb .low
    add di,2
    sub ax,16
.low:
    mov cl,al
    mov ax,1
    shl ax,cl
    ret

; Select matching drive + logical side-track, otherwise evict one of
; the two windows. Dirty victim must be flushed successfully first.
; Returns SI=window and CF=0 or CF=1 on failed victim flush.
cache_select:
    push ax
    push bx
    push cx
    push dx
    xor si,si
.search:
    mov al,1
    mov al,1
    mov cx,si
    shl al,cl
    test byte [cache_used],al
    jz .next
    mov al,[cur_disk]
    cmp al,[cache_drive+si]
    jne .next
    mov bx,si
    shl bx,1
    mov ax,[cur_track]
    cmp ax,[cache_track+bx]
    je .found
.next:
    inc si
    cmp si,2
    jb .search
    ; Prefer an unused window; otherwise use round-robin victim.
    xor si,si
    test byte [cache_used],1
    jz .allocate
    inc si
    test byte [cache_used],2
    jz .allocate
    xor si,si
    mov al,[cache_next]
    xor ah,ah
    mov si,ax
    call cache_flush_window
    jc .failure
.allocate:
    mov bx,si
    shl bx,1
    mov al,[cur_disk]
    mov [cache_drive+si],al
    mov ax,[cur_track]
    mov [cache_track+bx],ax
    mov bx,si
    shl bx,1
    shl bx,1
    mov word [cache_valid+bx],0
    mov word [cache_valid+bx+2],0
    mov word [cache_dirty+bx],0
    mov word [cache_dirty+bx+2],0
    mov ax,1
    mov cx,si
    shl al,cl
    or [cache_used],al
    mov ax,si
    xor al,1
    mov [cache_next],al
.found:
    mov [cache_slot],si
    clc
    jmp .done
.failure:
    stc
.done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; Ensure current physical sector is resident. A miss loads ONLY that
; 256-byte sector; neither the rest of the track nor dirty data is lost.
; All caller registers except flags preserved.
cache_ensure:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call cache_select
    jc .done
    mov bx,[cur_sector]
    shr bx,1
    call cache_bit
    test [cache_valid+di],ax
    jnz .hit
    ; Hardware READ can fail; don't set valid bit on failure.
    call sector_physical_read
    jc .done
    call cache_copy_in
    mov bx,[cur_sector]
    shr bx,1
    mov si,[cache_slot]
    call cache_bit
    or [cache_valid+di],ax
.hit:
    clc
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; Copy physical sector in fdc2d_buffer into active cache window.
cache_copy_in:
    push ax
    push cx
    push si
    push di
    push es
    mov si,[cache_slot]
    shl si,1
    mov ax,[cache_segments+si]
    mov es,ax
    mov di,[cur_sector]
    and di,0xfffe
    mov cl,7
    shl di,cl                   ; physical sector * 256
    mov si,fdc2d_buffer
    mov cx,128
    cld
    rep movsw
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; Copy one cached physical sector to DMA bounce buffer for write-back.
; SI=window, BX=physical sector; preserves all caller registers.
cache_copy_out:
    push ax
    push cx
    push si
    push di
    push ds
    push es
    mov di,si
    shl di,1
    mov ax,[cache_segments+di]
    mov ds,ax
    mov si,bx
    mov cl,8
    shl si,cl
    mov di,fdc2d_buffer
    push cs
    pop es
    mov cx,128
    cld
    rep movsw
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop ax
    ret

; Mark the currently selected physical sector dirty after 128-byte
; record copy. No host I/O until directory commit / eviction / WBOOT.
cache_mark_dirty:
    push ax
    push bx
    push cx
    push si
    push di
    mov si,[cache_slot]
    mov bx,[cur_sector]
    shr bx,1
    call cache_bit
    or [cache_dirty+di],ax
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; Flush a single window, writing only dirty physical sectors.
; SI=window; preserves all registers except CF. Do not clear a dirty bit
; until its physical WRITE succeeds. On failure, retain window and dirty
; mask; further cache replacement returns an error instead of data loss.
cache_flush_window:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov bx,0
.loop:
    call cache_bit
    test [cache_dirty+di],ax
    jz .next
    ; Save the BDOS-selected disk position; physical transport uses it.
    mov al,[cur_disk]
    mov [cache_saved_drive],al
    mov ax,[cur_track]
    mov [cache_saved_track],ax
    mov ax,[cur_sector]
    mov [cache_saved_sector],ax
    mov al,[cache_drive+si]
    mov [cur_disk],al
    mov di,si
    shl di,1
    mov ax,[cache_track+di]
    mov [cur_track],ax
    mov ax,bx
    shl ax,1
    mov [cur_sector],ax
    call cache_copy_out
    call sector_physical_write
    pushf
    mov al,[cache_saved_drive]
    mov [cur_disk],al
    mov ax,[cache_saved_track]
    mov [cur_track],ax
    mov ax,[cache_saved_sector]
    mov [cur_sector],ax
    popf
    jc .fail
    call cache_bit
    not ax
    and [cache_dirty+di],ax
.next:
    inc bx
    cmp bx,32
    jb .loop
    clc
    jmp .done
.fail:
    stc
.done:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; Flush both windows, including pending data for other drives.
cache_flush_all:
    push si
    xor si,si
    call cache_flush_window
    jc .done
    inc si
    call cache_flush_window
.done:
    pop si
    ret

; Drive name and track identify each window. Per-window valid + dirty
; masks describe only the sectors touched in that physical track.
cache_segments dw 0,0
cache_drive db 0xff,0xff
cache_track dw 0xffff,0xffff
cache_used db 0
cache_next db 0
cache_slot dw 0
cache_valid dw 0,0,0,0
cache_dirty dw 0,0,0,0
cache_saved_drive db 0
cache_saved_track dw 0
cache_saved_sector dw 0
cache_write_type db 0
%ifdef CBIOS_SELFTEST
cache_phys_reads dw 0
cache_phys_writes dw 0
%endif

; Common 256-byte physical transport from the earlier implementation.
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
