#!/usr/bin/env python3
"""Check arbitrary CP/M 8.3 file payloads in both FM-11 image builders."""
from pathlib import Path
from tempfile import TemporaryDirectory
from sys import path
path.insert(0, "tests")
import build_boot_2d as f2d
import build_boot_2hd as f2hd


def check_image(image, reserved, blocksize, files):
    directory = image[reserved:reserved + 64 * 32]
    for index, (name, contents) in enumerate(files):
        entry = directory[index*32:index*32+32]
        stem, suffix = f2d.cpm_name(Path(name))
        assert entry[0] == 0 and entry[1:9] == stem and entry[9:12] == suffix
        assert entry[15] == (len(contents)+127)//128
        required = (len(contents)+blocksize-1)//blocksize
        numbers = entry[16:16+required]
        reconstructed = b"".join(
            image[reserved+b*blocksize:reserved+(b+1)*blocksize] for b in numbers
        )
        assert reconstructed[:len(contents)] == contents, name


def main():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        payloads = [
            ("FDFORMAT.A86", b"cseg\r\nstart:\r\nend\r\n\x1a"),
            ("FDIPL.INC", bytes(range(256))*3),
            ("EMPTY.TXT", b""),
            ("DATA.DAT", bytes(range(251))*7),
        ]
        files = []
        for name,data in payloads:
            target = root/name
            target.write_bytes(data)
            files.append(target)
        bios = bytes([0xe9]) + bytes(0x18ff)
        core = bytes(0x2500)
        first = f2d.build_image(core,bios,files)
        second = f2hd.build_raw(core,bios,bytes(512),files)
        check_image(first, f2d.RESERVED_BYTES, f2d.BLOCK_SIZE, payloads)
        check_image(second, f2hd.RESERVED_BYTES, f2hd.BLOCK_BYTES, payloads)
        assert first[f2d.RESERVED_BYTES + 4*32] == 0xe5
        assert second[f2hd.RESERVED_BYTES + 4*32] == 0xe5
        duplicate = root/"fdformat.a86"
        duplicate.write_bytes(b"another")
        for builder in (
            lambda: f2d.build_image(core,bios,[files[0],duplicate]),
            lambda: f2hd.build_raw(core,bios,bytes(512),[files[0],duplicate])
        ):
            try:
                builder()
            except ValueError as error:
                assert "duplicate" in str(error).lower()
            else:
                raise AssertionError("case-insensitive 8.3 collision accepted")
        print("PASS: 2D/2HD image builders preserve arbitrary A86/INC/TXT/DAT files")


if __name__ == "__main__":
    main()
