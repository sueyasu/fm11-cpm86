SHELL := /bin/sh
NASM ?= nasm
PYTHON ?= python3
BUILD := build
CPM86_CORE ?= external/system/cpm86_core.bin

.PHONY: all check-tools check-core bios rom check test clean
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

bios: $(BUILD)/cbios.bin
rom: $(BUILD)/bootrom.bin

check: $(BUILD)/cbios.bin $(BUILD)/bootrom.bin
	$(PYTHON) tests/check_layout.py $(BUILD)/cbios.bin $(BUILD)/bootrom.bin

test: check

check-core:
	@test -f "$(CPM86_CORE)" || { echo "missing external CP/M-86 core: $(CPM86_CORE)" >&2; exit 1; }
	@test "$$(wc -c < '$(CPM86_CORE)')" -eq 9472 || { echo "CP/M-86 core must be 0x2500 bytes" >&2; exit 1; }

# A bootable disk is deliberately not produced until floppy IPL + BIOS I/O exist.
clean:
	rm -rf $(BUILD)
