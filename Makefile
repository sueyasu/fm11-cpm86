SHELL := /bin/sh
NASM ?= nasm
PYTHON ?= python3
BUILD := build
CPM86_CORE ?= external/system/cpm86_core.bin
EXTERNAL_COMMANDS := $(sort $(wildcard external/commands/*.CMD external/commands/*.cmd))

.PHONY: all check-tools check-core bios rom diag cbios-diag boot selftest check test clean
all: bios rom check

check-tools:
	@command -v $(NASM) >/dev/null || { echo "nasm is required" >&2; exit 1; }
	@command -v $(PYTHON) >/dev/null || { echo "python3 is required" >&2; exit 1; }

$(BUILD):
	mkdir -p $@

$(BUILD)/cbios.bin: src/cbios.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

# Self-test variant: same 21 entry vectors/CBIOS code, but INIT runs
# embedded diagnostics instead of entering CCP/BDOS.
$(BUILD)/cbios_selftest.bin: src/cbios.asm src/cbios_selftest.inc | $(BUILD)
	$(NASM) -DCBIOS_SELFTEST=1 -f bin $< -o $@

$(BUILD)/bootrom.bin: src/bootrom.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/iplrom.bin: src/iplrom.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/fm11_cpm86_2d.img: $(BUILD)/cbios.bin tests/build_boot_2d.py $(CPM86_CORE) $(EXTERNAL_COMMANDS) | $(BUILD)
	$(PYTHON) tests/build_boot_2d.py --core $(CPM86_CORE) --cbios $(BUILD)/cbios.bin \
		$(foreach f,$(EXTERNAL_COMMANDS),--file $(f)) $@

boot: check-core $(BUILD)/iplrom.bin $(BUILD)/fm11_cpm86_2d.img

# Only the disposable copy may be written by the test (last disk record).
# ASM86.CMD is fixed as the first entry for the READ-data assertion.
SELFTEST_ASM86 := $(firstword $(wildcard external/commands/ASM86.CMD external/commands/asm86.cmd))

$(BUILD)/fm11_cpm86_selftest_2d.img: $(BUILD)/cbios_selftest.bin tests/build_boot_2d.py $(CPM86_CORE) $(SELFTEST_ASM86) | $(BUILD)
	@test -n "$(SELFTEST_ASM86)" || { echo "missing external/commands/ASM86.CMD for self-test" >&2; exit 1; }
	$(PYTHON) tests/build_boot_2d.py --core $(CPM86_CORE) --cbios $(BUILD)/cbios_selftest.bin \
		--file "$(SELFTEST_ASM86)" $@

selftest: check-core $(BUILD)/iplrom.bin $(BUILD)/fm11_cpm86_selftest_2d.img
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

test: check diag cbios-diag $(BUILD)/iplrom.bin
	$(PYTHON) tests/check_diag.py $(BUILD)/fdc2d_diag.bin
	$(PYTHON) tests/check_cbios_diag.py $(BUILD)/cbios_diag.bin $(BUILD)/cbios_diag_2d.img $(BUILD)/cbios.bin
	$(PYTHON) tests/check_boot_2d.py $(BUILD)/iplrom.bin $(BUILD)/cbios.bin

check-core:
	@test -f "$(CPM86_CORE)" || { echo "missing external CP/M-86 core: $(CPM86_CORE)" >&2; exit 1; }
	@test "$$(wc -c < '$(CPM86_CORE)')" -eq 9472 || { echo "CP/M-86 core must be 0x2500 bytes" >&2; exit 1; }

# The boot target requires a separately supplied CP/M-86 resident core.
clean:
	rm -rf $(BUILD)
