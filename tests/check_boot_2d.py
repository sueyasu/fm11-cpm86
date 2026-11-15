#!/usr/bin/env python3
"""Static IPL and CP/M-86 2D filesystem tests using synthetic test files."""
import pathlib
import tempfile
import sys

from build_boot_2d import (
    BIOS_SIZE, CORE_SIZE, DISK_SIZE, RESERVED_BYTES, RESIDENT_SIZE,
    DIRECTORY_BYTES, BLOCK_SIZE, TOTAL_BLOCKS, build_image,
)


def check(rom, bios_path):
    bootrom = pathlib.Path(rom).read_bytes()
    bios = pathlib.Path(bios_path).read_bytes()
    assert len(bootrom) == 0x1000
    assert bootrom[0xFF0:0xFF5] == bytes((0xEA, 0, 0, 0, 0xFF))
    # The standalone IPL replaces the original FM-11 8088 boot ROM;
    # retain its 8259 ICW1/ICW2/ICW4 + OCW1 all-masked setup.
    assert bytes.fromhex(
        "B0 1B E6 00 B0 08 E6 01 B0 09 E6 01 B0 FF E6 01"
    ) in bootrom, "standalone IPL must initialize and mask the 8259 PIC"
    for phrase in (b"FM-11 CP/M-86 2D IPL: loading resident",
                   b"FM-11 CP/M-86 IPL: CBIOS vector OK, entering INIT",
                   b"FAIL: resident sector read / DMA"):
        assert phrase in bootrom
    assert len(bios) == BIOS_SIZE
    core = bytes(i & 0xFF for i in range(CORE_SIZE))
    image = build_image(core, bios)
    assert len(image) == DISK_SIZE
    assert image[:CORE_SIZE] == core
    assert image[CORE_SIZE:RESIDENT_SIZE] == bios
    assert image[RESIDENT_SIZE:RESERVED_BYTES] == (
        bytes([0xE5]) * (RESERVED_BYTES - RESIDENT_SIZE)
    )
    assert image[RESERVED_BYTES:RESERVED_BYTES + DIRECTORY_BYTES] == (
        bytes([0xE5]) * DIRECTORY_BYTES
    )
    try:
        build_image(core[:-1], bios)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong core size must be rejected")

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        sources = {}
        # Boundary cases: 0, 128, 256, and 257 records, plus partial blocks.
        for name, length in (
            ("EMPTY.CMD", 0),
            ("SMALL.CMD", 333),
            ("ONE.CMD", 128 * 128),
            ("TWO.CMD", 256 * 128),
            ("THREE.CMD", 257 * 128),
        ):
            payload = bytes((i * 7 + length) & 255 for i in range(length))
            p = root / name
            p.write_bytes(payload)
            sources[name] = (p, payload)
        disk = build_image(core, bios, [p for p, _ in sources.values()])
        assert disk[:RESIDENT_SIZE] == core + bios
        assert disk[RESIDENT_SIZE:RESERVED_BYTES] == image[
            RESIDENT_SIZE:RESERVED_BYTES
        ]

        entries = []
        blocks_used = set()
        for entry_number in range(64):
            start = RESERVED_BYTES + entry_number * 32
            entry = disk[start:start + 32]
            if entry[0] == 0xE5:
                continue
            assert entry[0] == 0              # user 0
            name = (entry[1:9].decode("ascii").rstrip() + "." +
                    entry[9:12].decode("ascii").rstrip())
            extent = entry[12] + 32 * entry[14]
            rc = entry[15]
            assert 0 <= rc <= 128
            allocation = [n for n in entry[16:32] if n]
            for block in allocation:
                assert 1 <= block < TOTAL_BLOCKS
                assert block not in blocks_used
                blocks_used.add(block)
            entries.append((name, extent, rc, allocation))

        assert len(entries) == 6  # THREE.CMD spans two entries
        by_name = {}
        for name, extent, rc, blocks in entries:
            by_name.setdefault(name, []).append((extent, rc, blocks))
        assert set(by_name) == set(sources)
        assert [(ex, rc) for ex, rc, _ in by_name["EMPTY.CMD"]] == [(0, 0)]
        assert [(ex, rc) for ex, rc, _ in by_name["ONE.CMD"]] == [(0, 128)]
        assert [(ex, rc) for ex, rc, _ in by_name["TWO.CMD"]] == [(1, 128)]
        assert [(ex, rc) for ex, rc, _ in by_name["THREE.CMD"]] == [
            (1, 128), (2, 1)
        ]

        for name, (path, payload) in sources.items():
            restored = bytearray()
            for extent, rc, blocks in sorted(by_name[name]):
                for block in blocks:
                    off = RESERVED_BYTES + block * BLOCK_SIZE
                    restored.extend(disk[off:off + BLOCK_SIZE])
            assert restored[:len(payload)] == payload, name

        # Case-insensitive CP/M namespace and filesystem capacity checks.
        try:
            build_image(core, bios, [sources["SMALL.CMD"][0]] * 2)
        except ValueError as exc:
            assert "duplicate" in str(exc)
        else:
            raise AssertionError("duplicate filename accepted")

        invalid = root / "TOO-LONG9.CMD"  # nine-character stem (invalid 8.3)
        invalid.write_bytes(b"x")
        try:
            build_image(core, bios, [invalid])
        except ValueError as exc:
            assert "8.3" in str(exc)
        else:
            raise AssertionError("invalid 8.3 name accepted")

        huge = root / "HUGE.CMD"
        huge.write_bytes(bytes(310_000))
        try:
            build_image(core, bios, [huge])
        except ValueError as exc:
            assert "full" in str(exc)
        else:
            raise AssertionError("full disk accepted")

        many = []
        for i in range(65):
            p = root / f"F{i:03d}.CMD"
            p.write_bytes(b"")
            many.append(p)
        try:
            build_image(core, bios, many)
        except ValueError as exc:
            assert "directory" in str(exc)
        else:
            raise AssertionError("directory overflow accepted")

    print("PASS: IPL ROM, 2D image, CMD directory, extents and allocation maps")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_boot_2d.py IPLROM.bin CBIOS.bin")
    check(*sys.argv[1:])
