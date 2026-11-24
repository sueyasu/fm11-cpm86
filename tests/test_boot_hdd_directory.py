#!/usr/bin/env python3
"""Regression: whole-HDD boot image checking accepts real CP/M file entries."""
from pathlib import Path
from tempfile import TemporaryDirectory

from build_boot_hdd import build_image, BLOCK, MODELS, SPT, SECTOR
from check_boot_hdd import check


def main():
    root = Path("build")
    ipl = (root / "ipl_hdd.bin").read_bytes()
    cbios = (root / "cbios_hdd.bin").read_bytes()
    core = bytes(0x2500)
    model = "m2230b"
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        a86 = folder / "FDFORMAT.A86"
        inc = folder / "FDIPL2D.INC"
        cmd = folder / "ASM86.CMD"
        a86.write_bytes(b"CSEG\r\nSTART:\r\nEND\r\n\x1a")
        inc.write_bytes(bytes(range(256)) * 4)
        cmd.write_bytes(b"CMD" * 3000)
        files = [a86, inc, cmd]
        image = build_image(model, ipl, core, cbios, files)
        check(ipl, cbios, image, model)
        heads = MODELS[model][1]
        directory_start = heads * SPT * SECTOR
        directory = image[directory_start:directory_start + BLOCK]
        for entry_idx, file in enumerate(files):
            entry = directory[entry_idx * 32:(entry_idx + 1) * 32]
            stem, ext = file.name.split(".")
            assert entry[1:9] == stem.ljust(8).encode()
            assert entry[9:12] == ext.ljust(3).encode()
            block = int.from_bytes(entry[16:18], "little")
            assert block >= 1
            start = directory_start + block * BLOCK
            assert image[start:start + len(file.read_bytes())] == file.read_bytes()
        assert directory[len(files) * 32] == 0xe5
        # Reject an overlapping allocation in a different entry.
        corrupt = bytearray(image)
        corrupt[directory_start + 32 + 16:directory_start + 32 + 18] = (
            directory[16:18]
        )
        try:
            check(ipl, cbios, corrupt, model)
        except AssertionError as exc:
            assert "duplicate block" in str(exc)
        else:
            raise AssertionError("overlapping HDD allocations accepted")
    print("PASS: populated HDD directory and file data, duplicate block rejection")


if __name__ == "__main__":
    main()
