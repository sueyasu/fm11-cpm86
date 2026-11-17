; HDIO.INC -- common 8086 native FM-11 MDC HDD routines.
; INCLUDE from CSEG. External DSEG symbols declared in each caller:
; hd_buffer (512 bytes), hd_result (10), hd_cyl (word), hd_head/hd_sec
; hd_heads, hd_cylinders, hd_dma_ptr, hd_rw.
; All I/O uses a single physical MDC unit and 8237 channel 2.
; Public entry: hd_open, hd_read_sector, hd_write_sector.
; CF clear on success. No ROM BIOS or PC-98 SCSI calls.

hd_open:
        ; Select physical drive zero and DMA channel 2.
        mov     dx,HD_PORT_SEL
        mov     al,020h
        out     dx,al
        ; Sense drive model and geometry from its hardware type code.
        mov     dx,HD_PORT_CMD
        mov     al,HD_SENSE
        out     dx,al
        mov     dx,HD_PORT_DATA
        xor     al,al
        out     dx,al
        out     dx,al
        call    hd_wait_result
        jc      hd_open_bad
        mov     bx,offset hd_result
        add     bx,4
        mov     al,[bx]
        cmp     al,004h
        jne     hd_type08
        mov     Word Ptr hd_cylinders,157
        mov     Byte Ptr hd_heads,4
        jmp     hd_type_found
hd_type08:
        cmp     al,008h
        jne     hd_type05
        mov     Word Ptr hd_cylinders,315
        mov     Byte Ptr hd_heads,2
        jmp     hd_type_found
hd_type05:
        cmp     al,005h
        jne     hd_type09
        mov     Word Ptr hd_cylinders,157
        mov     Byte Ptr hd_heads,6
        jmp     hd_type_found
hd_type09:
        cmp     al,009h
        jne     hd_type0a
        mov     Word Ptr hd_cylinders,315
        mov     Byte Ptr hd_heads,4
        jmp     hd_type_found
hd_type0a:
        cmp     al,00ah
        jne     hd_type0c
        mov     Word Ptr hd_cylinders,315
        mov     Byte Ptr hd_heads,6
        jmp     hd_type_found
hd_type0c:
        cmp     al,00ch
        jne     hd_type14
        mov     Word Ptr hd_cylinders,315
        mov     Byte Ptr hd_heads,8
        jmp     hd_type_found
hd_type14:
        cmp     al,014h
        jne     hd_type15
        mov     Word Ptr hd_cylinders,747
        mov     Byte Ptr hd_heads,4
        jmp     hd_type_found
hd_type15:
        cmp     al,015h
        jne     hd_type16
        mov     Word Ptr hd_cylinders,747
        mov     Byte Ptr hd_heads,7
        jmp     hd_type_found
hd_type16:
        cmp     al,016h
        jne     hd_open_bad
        mov     Word Ptr hd_cylinders,747
        mov     Byte Ptr hd_heads,11
hd_type_found:
        ; Binary addressing is unnecessary: CHS is direct and avoids
        ; 32-bit logical-sector arithmetic on the 8086.
        mov     dx,HD_PORT_CMD
        mov     al,HD_MODE
        out     dx,al
        mov     dx,HD_PORT_DATA
        mov     al,060h
        out     dx,al
        xor     al,al
        out     dx,al
        call    hd_wait_result
        ret
hd_open_bad:
        stc
        ret

hd_wait_result:
        push    bx
        push    cx
        push    dx
        mov     dx,HD_PORT_CMD
        mov     cx,0ffffh
hd_wr_poll:
        in      al,dx
        test    al,040h
        jnz     hd_wr_ready
        loop    hd_wr_poll
        jmp     hd_wr_error
hd_wr_ready:
        mov     dx,HD_PORT_DATA
        mov     bx,offset hd_result
        mov     cx,10
hd_wr_bytes:
        in      al,dx
        mov     [bx],al
        inc     bx
        loop    hd_wr_bytes
        mov     al,Byte Ptr hd_result
        test    al,080h
        jnz     hd_wr_error
        clc
        jmp     hd_wr_done
hd_wr_error:
        stc
hd_wr_done:
        pop     dx
        pop     cx
        pop     bx
        ret

hd_read_sector:
        mov     Byte Ptr hd_rw,0
        call    hd_sector_io
        ret
hd_write_sector:
        mov     Byte Ptr hd_rw,1
        call    hd_sector_io
        ret

; Data at hd_buffer[0..255]. The second 256-byte slot serves as
; alternative DMA memory when the first one crosses a 64 KiB page.
hd_sector_io:
        push    ax
        push    bx
        push    cx
        push    dx
        push    si
        push    di
        push    es
        ; Protect against invalid CHS before issuing any command.
        mov     ax,Word Ptr hd_cyl
        cmp     ax,Word Ptr hd_cylinders
        jae     hd_io_bad
        mov     al,Byte Ptr hd_head
        cmp     al,Byte Ptr hd_heads
        jae     hd_io_bad
        cmp     Byte Ptr hd_sec,HD_SPT
        jae     hd_io_bad

        mov     Word Ptr hd_dma_ptr,offset hd_buffer
        mov     ax,ds
        mov     bx,16
        mul     bx
        add     ax,offset hd_buffer
        adc     dx,0
        cmp     ax,HD_DMA_LIMIT
        jbe     hd_dma_in_page
        add     Word Ptr hd_dma_ptr,HD_BUF_SIZE
        add     ax,HD_BUF_SIZE
        adc     dx,0
hd_dma_in_page:
        cmp     dx,15
        ja      hd_io_bad
        mov     Word Ptr hd_dma_addr,ax
        mov     Byte Ptr hd_dma_bank,dl

        cmp     Byte Ptr hd_rw,0
        je      hd_dma_prepare
        mov     si,offset hd_buffer
        mov     di,Word Ptr hd_dma_ptr
        push    ds
        pop     es
        mov     cx,128
        cld
        rep     movsw
hd_dma_prepare:
        ; 8237 address/count and mode for channel 2.
        mov     dx,01ah
        mov     al,6
        out     dx,al
        mov     dx,01ch
        xor     al,al
        out     dx,al
        mov     dx,014h
        mov     ax,Word Ptr hd_dma_addr
        out     dx,al
        mov     al,ah
        out     dx,al
        mov     dx,015h
        mov     al,0ffh
        out     dx,al
        xor     al,al
        out     dx,al
        mov     dx,022h
        mov     al,Byte Ptr hd_dma_bank
        out     dx,al
        mov     dx,01bh
        mov     al,046h
        cmp     Byte Ptr hd_rw,0
        je      hd_dma_mode
        mov     al,04ah
hd_dma_mode:
        out     dx,al
        mov     dx,018h
        in      al,dx
        mov     dx,01ah
        mov     al,2
        out     dx,al

        ; Issue 256-byte CHS READ(22h) or WRITE(23h).
        mov     dx,HD_PORT_CMD
        mov     al,HD_READ
        cmp     Byte Ptr hd_rw,0
        je      hd_mdc_command
        mov     al,HD_WRITE
hd_mdc_command:
        out     dx,al
        mov     dx,HD_PORT_DATA
        xor     al,al
        out     dx,al                ; drive 0
        out     dx,al                ; reserved
        mov     ax,Word Ptr hd_cyl
        mov     al,ah
        out     dx,al                ; cyl high
        mov     ax,Word Ptr hd_cyl
        out     dx,al                ; cyl low
        mov     al,Byte Ptr hd_head
        out     dx,al
        mov     al,Byte Ptr hd_sec
        out     dx,al
        mov     al,1
        out     dx,al                ; byte count high 01h
        xor     al,al
        out     dx,al                ; byte count low 00h
        call    hd_wait_result
        jc      hd_io_bad
        mov     dx,018h
        in      al,dx
        test    al,4                ; channel 2 terminal count
        jz      hd_io_bad
        cmp     Byte Ptr hd_rw,0
        jne     hd_io_good
        mov     si,Word Ptr hd_dma_ptr
        mov     di,offset hd_buffer
        push    ds
        pop     es
        mov     cx,128
        cld
        rep     movsw
hd_io_good:
        clc
        jmp     hd_io_finish
hd_io_bad:
        stc
hd_io_finish:
        pushf
        mov     dx,01ah
        mov     al,6
        out     dx,al
        popf
        pop     es
        pop     di
        pop     si
        pop     dx
        pop     cx
        pop     bx
        pop     ax
        ret

