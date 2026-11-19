SHELL := /bin/sh
NASM ?= nasm
PYTHON ?= python3
BUILD := build
CPM86_CORE ?= external/system/cpm86_core.bin
# Import all CP/M-compatible 8.3 files (CMD/A86/INC/TXT/etc.).
# README.md is host-only documentation; CP/M 8.3 names are validated by
# both image builders before a disk image is written.
EXTERNAL_FILES := $(filter-out external/commands/README.md,$(sort $(wildcard external/commands/*)))

.PHONY: all check-tools check-core bios rom diag cbios-diag boot boot-d88 boot-2hd boot-hdd hddipl-inc format-inc selftest check test clean
all: bios rom check

check-tools:
	@command -v $(NASM) >/dev/null || { echo "nasm is required" >&2; exit 1; }
	@command -v $(PYTHON) >/dev/null || { echo "python3 is required" >&2; exit 1; }

$(BUILD):
	mkdir -p $@

$(BUILD)/cbios.bin: src/cbios.asm src/cbios_local_console.inc src/cbios_ansi.inc src/cbios_hdd.inc src/cbios_track_cache.inc | $(BUILD)
	$(NASM) -f bin $< -o $@

# The 2HD bootable image starts at logical E:, while the 2D image starts at A:.
$(BUILD)/cbios_2hd.bin: src/cbios.asm src/cbios_local_console.inc src/cbios_ansi.inc src/cbios_hdd.inc src/cbios_track_cache.inc | $(BUILD)
	$(NASM) -f bin -DBOOT_DRIVE=4 $< -o $@

# Link the self-test into the CCP/BDOS-sized core region. Keep the
# actual CBIOS at exactly 0x1900 bytes, preserving the normal IPL layout.
$(BUILD)/cbios_selftest_resident.bin: src/cbios_selftest_resident.asm src/cbios.asm src/cbios_local_console.inc src/cbios_ansi.inc src/cbios_hdd.inc src/cbios_track_cache.inc src/cbios_selftest.inc | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/cbios_selftest_core.bin $(BUILD)/cbios_selftest.bin &: $(BUILD)/cbios_selftest_resident.bin tests/split_selftest_resident.py
	$(PYTHON) tests/split_selftest_resident.py $(BUILD)/cbios_selftest_resident.bin $(BUILD)/cbios_selftest_core.bin $(BUILD)/cbios_selftest.bin

# Alternate serial-console binaries, useful for existing PTY workflows.
# The on-disk resident layout and boot-drive patch offset stay unchanged.
$(BUILD)/cbios_serial.bin: src/cbios.asm src/cbios_local_console.inc src/cbios_ansi.inc src/cbios_hdd.inc src/cbios_track_cache.inc | $(BUILD)
	$(NASM) -f bin -DCONSOLE_LOCAL=0 $< -o $@

$(BUILD)/iplrom_serial.bin: src/iplrom.asm | $(BUILD)
	$(NASM) -f bin -DCONSOLE_LOCAL=0 $< -o $@

$(BUILD)/hdd_bootrom_serial.bin: src/hdd_bootrom.asm src/hdd_boot_io.inc | $(BUILD)
	$(NASM) -f bin -DCONSOLE_LOCAL=0 $< -o $@

$(BUILD)/bootrom.bin: src/bootrom.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/iplrom.bin: src/iplrom.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

# 512-byte disk IPL, distinct from the 4-KiB reset ROM.
$(BUILD)/ipl_2d.bin: src/ipl_2d.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/ipl_2hd.bin: src/ipl_2hd.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

# CP/M-86 ASM86 includes: generated from the exact disk IPL binaries.
# These files are consumed by command/FORMAT.A86 under CP/M-86.
command/FDIPL2D.INC: $(BUILD)/ipl_2d.bin command/bin2a86.py
	$(PYTHON) command/bin2a86.py $< $@ --label fdipl2d_template --expect-size 512

command/FDIPL2HD.INC: $(BUILD)/ipl_2hd.bin command/bin2a86.py
	$(PYTHON) command/bin2a86.py $< $@ --label fdipl2hd_template --expect-size 512

command/HDIPL.INC: $(BUILD)/ipl_hdd.bin command/bin2a86.py
	$(PYTHON) command/bin2a86.py $< $@ --label hdipl_template --expect-size 512

hddipl-inc: command/HDIPL.INC

# ASM86 FORMAT.A86 requires all three disk IPL include files.
format-inc: command/FDIPL2D.INC command/FDIPL2HD.INC command/HDIPL.INC

$(BUILD)/fm11_cpm86_2d.img: $(BUILD)/cbios.bin tests/build_boot_2d.py $(CPM86_CORE) $(EXTERNAL_FILES) | $(BUILD)
	$(PYTHON) tests/build_boot_2d.py --core $(CPM86_CORE) --cbios $(BUILD)/cbios.bin \
		$(foreach f,$(EXTERNAL_FILES),--file $(f)) $@

boot: check-core $(BUILD)/iplrom.bin $(BUILD)/fm11_cpm86_2d.img

$(BUILD)/fm11_cpm86_boot_2d.d88: $(BUILD)/fm11_cpm86_2d.img $(BUILD)/ipl_2d.bin tests/build_boot_d88.py | $(BUILD)
	$(PYTHON) tests/build_boot_d88.py --raw $(BUILD)/fm11_cpm86_2d.img \
		--ipl $(BUILD)/ipl_2d.bin --raw-output $(BUILD)/fm11_cpm86_boot_2d.raw \
		--output $@

boot-d88: check-core $(BUILD)/fm11_cpm86_boot_2d.d88
	$(PYTHON) tests/check_boot_d88.py $(BUILD)/fm11_cpm86_2d.img \
		$(BUILD)/ipl_2d.bin $(BUILD)/fm11_cpm86_boot_2d.d88 \
		$(BUILD)/fm11_cpm86_boot_2d.raw


# Native FM-11 2HD: mixed 128-byte FM boot track / 256-byte MFM tracks.
# The 2HD resident is built separately with cold-start drive E:.
$(BUILD)/fm11_cpm86_boot_2hd.d88: $(BUILD)/cbios_2hd.bin $(BUILD)/ipl_2hd.bin tests/build_boot_2hd.py tests/build_boot_2d.py $(CPM86_CORE) $(EXTERNAL_FILES) | $(BUILD)
	$(PYTHON) tests/build_boot_2hd.py --core $(CPM86_CORE) --cbios $(BUILD)/cbios_2hd.bin \
		--ipl $(BUILD)/ipl_2hd.bin $(foreach f,$(EXTERNAL_FILES),--file $(f)) \
		--raw-output $(BUILD)/fm11_cpm86_boot_2hd.raw --output $@

boot-2hd: check-core $(BUILD)/fm11_cpm86_boot_2hd.d88
	$(PYTHON) tests/check_boot_2hd.py $(BUILD)/ipl_2hd.bin $(BUILD)/cbios_2hd.bin \
		$(BUILD)/fm11_cpm86_boot_2hd.raw $(BUILD)/fm11_cpm86_boot_2hd.d88


# FM-11 MDC whole-HDD CP/M-86 I: (no partition table).
# The reset ROM loads the on-disk 512-byte IPL, which loads the 0x3E00
# resident image. Geometry defaults to M2233B; choose HDD_MODEL=m2243b etc.
HDD_MODEL ?= m2233b

.PHONY: hdd_image_force
hdd_image_force:


$(BUILD)/cbios_hdd.bin: src/cbios.asm src/cbios_local_console.inc src/cbios_ansi.inc src/cbios_hdd.inc src/cbios_track_cache.inc | $(BUILD)
	$(NASM) -f bin -DBOOT_DRIVE=8 $< -o $@

$(BUILD)/ipl_hdd.bin: src/ipl_hdd.asm src/hdd_boot_io.inc | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/hdd_bootrom.bin: src/hdd_bootrom.asm src/hdd_boot_io.inc | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/fm11_cpm86_boot_hdd.img: hdd_image_force $(BUILD)/cbios_hdd.bin $(BUILD)/ipl_hdd.bin tests/build_boot_hdd.py tests/build_boot_2d.py $(CPM86_CORE) $(EXTERNAL_FILES) | $(BUILD)
	$(PYTHON) tests/build_boot_hdd.py --model $(HDD_MODEL) \
		--ipl $(BUILD)/ipl_hdd.bin --core $(CPM86_CORE) --cbios $(BUILD)/cbios_hdd.bin \
		$(foreach f,$(EXTERNAL_FILES),--file $(f)) $@

boot-hdd: check-core $(BUILD)/hdd_bootrom.bin $(BUILD)/fm11_cpm86_boot_hdd.img
	$(PYTHON) tests/check_boot_hdd.py $(BUILD)/hdd_bootrom.bin $(BUILD)/ipl_hdd.bin $(BUILD)/cbios_hdd.bin $(BUILD)/fm11_cpm86_boot_hdd.img $(HDD_MODEL)

$(BUILD)/test_hdd.img: $(BUILD)/test_2hd_core.bin $(BUILD)/cbios_hdd.bin $(BUILD)/ipl_hdd.bin tests/build_boot_hdd.py | $(BUILD)
	$(PYTHON) tests/build_boot_hdd.py --model m2230b \
		--ipl $(BUILD)/ipl_hdd.bin --core $(BUILD)/test_2hd_core.bin --cbios $(BUILD)/cbios_hdd.bin $@

# Structural 2HD tests use a deliberately nonbootable synthetic CCP/BDOS.
# No proprietary CP/M core is necessary to run "make test".
$(BUILD)/test_2hd_core.bin: | $(BUILD)
	$(PYTHON) -c "from pathlib import Path; Path('$@').write_bytes(bytes(0x2500))"

$(BUILD)/test_2hd.d88: $(BUILD)/test_2hd_core.bin $(BUILD)/cbios_2hd.bin $(BUILD)/ipl_2hd.bin tests/build_boot_2hd.py | $(BUILD)
	$(PYTHON) tests/build_boot_2hd.py --core $(BUILD)/test_2hd_core.bin --cbios $(BUILD)/cbios_2hd.bin \
		--ipl $(BUILD)/ipl_2hd.bin --raw-output $(BUILD)/test_2hd.raw --output $@

# Only the disposable copy may be written by the test (last disk record).
# ASM86.CMD is fixed as the first entry for the READ-data assertion.
SELFTEST_ASM86 := $(firstword $(wildcard external/commands/ASM86.CMD external/commands/asm86.cmd))

$(BUILD)/fm11_cpm86_selftest_2d.img: $(BUILD)/cbios_selftest_core.bin $(BUILD)/cbios_selftest.bin tests/build_boot_2d.py $(SELFTEST_ASM86) | $(BUILD)
	@test -n "$(SELFTEST_ASM86)" || { echo "missing external/commands/ASM86.CMD for self-test" >&2; exit 1; }
	$(PYTHON) tests/build_boot_2d.py --core $(BUILD)/cbios_selftest_core.bin --cbios $(BUILD)/cbios_selftest.bin \
		--file "$(SELFTEST_ASM86)" $@

selftest: $(BUILD)/iplrom.bin $(BUILD)/fm11_cpm86_selftest_2d.img
	$(PYTHON) tests/check_layout.py $(BUILD)/cbios_selftest.bin $(BUILD)/iplrom.bin
	@echo "SELFTEST: boot with build/iplrom.bin and build/fm11_cpm86_selftest_2d.img"
	@echo "WARNING: self-test writes/restores the last record; use only this disposable image."



$(BUILD)/fdc2d_diag.bin: src/fdc2d_diag.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/cbios_diag.bin: src/cbios_diag.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/cbios_diag_2d.img: $(BUILD)/cbios.bin tests/build_cbios_diag_disk.py | $(BUILD)
	$(PYTHON) tests/build_cbios_diag_disk.py $(BUILD)/cbios.bin $@

cbios-diag: $(BUILD)/cbios_diag.bin $(BUILD)/cbios_diag_2d.img

bios: $(BUILD)/cbios.bin
rom: $(BUILD)/bootrom.bin
diag: $(BUILD)/fdc2d_diag.bin

check: $(BUILD)/cbios.bin $(BUILD)/bootrom.bin
	$(PYTHON) tests/check_layout.py $(BUILD)/cbios.bin $(BUILD)/bootrom.bin

test: check diag cbios-diag $(BUILD)/iplrom.bin $(BUILD)/test_2hd.d88 $(BUILD)/test_hdd.img $(BUILD)/hdd_bootrom.bin $(BUILD)/cbios_serial.bin $(BUILD)/iplrom_serial.bin $(BUILD)/hdd_bootrom_serial.bin format-inc
	$(PYTHON) tests/check_boot_2hd.py $(BUILD)/ipl_2hd.bin $(BUILD)/cbios_2hd.bin \
		$(BUILD)/test_2hd.raw $(BUILD)/test_2hd.d88
	$(PYTHON) tests/check_fdformat_inc.py $(BUILD)/ipl_2d.bin $(BUILD)/ipl_2hd.bin command/FDIPL2D.INC command/FDIPL2HD.INC
	$(PYTHON) tests/check_boot_hdd.py $(BUILD)/hdd_bootrom.bin $(BUILD)/ipl_hdd.bin $(BUILD)/cbios_hdd.bin $(BUILD)/test_hdd.img m2230b
	$(PYTHON) tests/test_boot_hdd_directory.py
	$(PYTHON) tests/check_format_source.py
	$(PYTHON) tests/check_fdformat_boot_patch.py $(BUILD)/cbios.bin $(BUILD)/cbios_2hd.bin $(BUILD)/cbios_hdd.bin
	$(PYTHON) tests/check_image_files.py
	$(PYTHON) tests/check_local_console.py
	$(PYTHON) tests/check_ansi_console.py
	$(PYTHON) tests/check_ansitest_source.py
	$(PYTHON) tests/check_iobyte.py
	$(PYTHON) tests/check_ram_mrt.py $(BUILD)/cbios.bin
	$(PYTHON) tests/check_cbios_segments.py
	$(PYTHON) tests/check_sector_cache.py
	$(PYTHON) tests/check_io_retry.py
	$(PYTHON) tests/check_cache_api.py $(BUILD)/cbios.bin $(BUILD)/cbios_2hd.bin $(BUILD)/cbios_hdd.bin $(BUILD)/cbios_serial.bin
	$(PYTHON) tests/check_diag.py $(BUILD)/fdc2d_diag.bin
	$(PYTHON) tests/check_cbios_diag.py $(BUILD)/cbios_diag.bin $(BUILD)/cbios_diag_2d.img $(BUILD)/cbios.bin
	$(PYTHON) tests/check_boot_2d.py $(BUILD)/iplrom.bin $(BUILD)/cbios.bin

check-core:
	@test -f "$(CPM86_CORE)" || { echo "missing external CP/M-86 core: $(CPM86_CORE)" >&2; exit 1; }
	@test "$$(wc -c < '$(CPM86_CORE)')" -eq 9472 || { echo "CP/M-86 core must be 0x2500 bytes" >&2; exit 1; }

# The boot target requires a separately supplied CP/M-86 resident core.
clean:
	rm -rf $(BUILD)
