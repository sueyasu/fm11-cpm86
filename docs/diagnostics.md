# 診断・開発用ビルド

通常の利用には不要です。起動イメージの作成は [BUILD.md](../BUILD.md) を参照してください。

## 自動検査

```sh
make test
```

外部CCP/BDOSコアは不要です。NASMでのアセンブル、CBIOSサイズと固定ABI、ディスクイメージ構造、RAM検出、コンソール、キャッシュ、I/Oリトライなどを静的に検査します。GitHub Actionsでも実行されます。エミュレータ実行や実機での動作を保証するものではありません。

## 診断ROM

`make` で生成する `build/bootrom.bin` はシリアル出力後に停止する診断ROMであり、CP/M-86起動用ROMではありません。

```sh
make diag
make cbios-diag
```

前者は `build/fdc2d_diag.bin` を生成します。2D FDD 0の先頭256バイトをDMAで読み取る非破壊診断です。後者は `build/cbios_diag.bin` と `build/cbios_diag_2d.img` を生成します。専用ディスクを2D FDD 0に接続し、対応する診断ROMを8088ブートROMとして指定します。シリアルPTYに接続し、キーを一つ入力すると検査を開始します。

CBIOS診断ではREAD、WRITE、半セクタの保持、読み戻し、元のデータの復元を検査します。**専用の使い捨てイメージ以外では実行しないでください。**

## 内蔵セルフテスト

詳細は [cbios-selftest.md](cbios-selftest.md) を参照してください。

## 旧READMEに記載されていた診断手順（開発記録）

以下は開発当時の記録です。現行の利用仕様ではありません。

## Read-only 2D FDC diagnostic

A separate firmware image tests one physical Mini-FDC sector without
loading CP/M-86 or modifying the disk:

```sh
make diag
make test
```

This produces `build/fdc2d_diag.bin` (4096 bytes). Configure the emulator
for the 8088 card, mount a **2D** floppy image on the Mini FDC's **unit 0**,
and start `fm11-sdl` with:

```sh
fm11-sdl --8088-rom build/fdc2d_diag.bin
```

The diagnostic ROM waits for one received serial byte before printing anything.
After launching fm11-sdl, note the `Serial PTY: /dev/pts/N` path printed
in its terminal. Open a second terminal, connect with
`screen /dev/pts/N` (or `picocom`), then press any key to start
the diagnostic. This prevents startup output from being missed.
The ROM reads physical cylinder 0, head 0, sector 1 (256 bytes) through
8237 DMA channel 0 into physical RAM 0000:2000. It checks FDC completion
and DMA terminal count, then prints the first 16 bytes in hexadecimal.
Expected output begins with:

```text
FM-11 2D DMA read C0/H0/S1
PASS: TC=1, data: ...
```

On failure it prints `FAIL: FDC status or DMA terminal count`.
**No WRITE SECTOR command is issued**, so the diagnostic does not alter
the floppy. This is a hardware-path test, not a full execution test of
CBIOS `READ`/`WRITE` or of the 128-byte record mapping. The
`fm11-8088-romtrace` standalone tool does not mount a disk, so it is
not sufficient for a successful floppy-read test. `make test` performs
static ROM checks only; a successful test is not a claim of emulated or
physical I/O success.

## CBIOS READ/WRITE integration diagnostic

Build a **dedicated disposable 2D test image** and 8088 diagnostic ROM:

```sh
make cbios-diag
make test
```

Outputs: `build/cbios_diag.bin` (4096-byte ROM) and
`build/cbios_diag_2d.img` (327680-byte raw 2D floppy). Never use
a disk containing valuable data for this test. The generated image
contains the actual `build/cbios.bin` at C0/H0/S2 onward, followed
by a scratch sector at C1/H0/S1. The diagnostic ROM loads all 25
physical sectors (0x1900 bytes) of the real CBIOS to RAM
0000:2500, then calls its existing 21-entry vector table.
It does **not** enter the unfinished INIT/WBOOT or require the
external CP/M-86 CCP/BDOS core.

With the 8088 selected as the main CPU in `/etc/fm11emu.conf`,
start the SDL frontend using your normal 6809 main-board ROM (required
for SDL floppy mounting) and the dedicated raw image:

```sh
fm11-sdl --main-rom /path/to/boot6809.bin \\
  --8088-rom build/cbios_diag.bin \\
  --floppy2d build/cbios_diag_2d.img --floppy-drive 0
```

The ROM waits for one incoming serial byte before it starts: attach
`screen /dev/pts/N` to the `Serial PTY:` announced by fm11-sdl,
and press any key.

Expected serial output:

```text
CBIOS 128-byte record test
CBIOS loaded from 2D disk
PASS: records 0 and 1 read
PASS: WRITE, RMW, verify, restore
```

The diagnostic now prints `STEP:` markers around the first CBIOS
calls, including `SELDSK` and the two logical `READ` operations.
If `fm11-sdl` reports an invalid opcode, capture the last printed
`STEP:` marker. The cross-segment call gate resides at 0000:7100
and uses only 8086 PUSH/RET instructions, avoiding the previous
FF-group indirect CALL. An emulator exception alone does not prove a
CBIOS disk failure; the step markers distinguish dispatch failure from
the actual FDC/record transfer.

The ROM selects drive A:, track 2 (physical C1/H0), and reads logical
records 0 and 1 into distinct RAM buffers. It checks both expected
byte patterns. It then writes a third pattern into record 0, reads
it back, confirms that record 1 was preserved, and restores the
original record 0. A failed write or restore can still leave the
disposable scratch sector modified. This is a functional test of
CBIOS `READ`/`WRITE`, not just direct FDC register access. The
serial output, not the static `make test` result, establishes whether
the emulated FDC, DMA, and CBIOS work together.

