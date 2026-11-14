SHELL := /bin/sh
NASM ?= nasm
PYTHON ?= python3
BUILD := build
CPM86_CORE ?= external/system/cpm86_core.bin

.PHONY: all check-tools check-core bios rom diag cbios-diag check test clean
all: bios rom check

check-tools:
	@command -v $(NASM) >/dev/null || { echo "nasm is required" >&2; exit 1; }
	@command -v $(PYTHON) >/dev/null || { echo "python3 is required" >&2; exit 1; }

$(BUILD):
	mkdir -p $@

$(BUILD)/cbios.bin: src/cbios.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/bootrom.bin: src/bootrom.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

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

test: check diag cbios-diag
	$(PYTHON) tests/check_diag.py $(BUILD)/fdc2d_diag.bin
	$(PYTHON) tests/check_cbios_diag.py $(BUILD)/cbios_diag.bin $(BUILD)/cbios_diag_2d.img $(BUILD)/cbios.bin

check-core:
	@test -f "$(CPM86_CORE)" || { echo "missing external CP/M-86 core: $(CPM86_CORE)" >&2; exit 1; }
	@test "$$(wc -c < '$(CPM86_CORE)')" -eq 9472 || { echo "CP/M-86 core must be 0x2500 bytes" >&2; exit 1; }

# A bootable disk is deliberately not produced until floppy IPL + BIOS I/O exist.
clean:
	rm -rf $(BUILD)
