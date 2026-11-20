# 起動イメージの作成と起動方法

## 必要なツール

Linux上で次のツールを用意してください。

- make
- NASM
- Python 3

通常のイメージ生成にはcpmtoolsは不要です。

## CP/M-86 CCP/BDOSコアの準備

本リポジトリにはFM-11用のIPLとCBIOSのソースを収録しています。CP/M-86 v1.1の互換性のあるCCP/BDOSコア（常駐イメージの先頭0x2500バイト、9472バイト）は別途用意し、次のファイルに格納してください。

```text
external/system/cpm86_core.bin
```

既存の本移植用2D起動RAWイメージ（ディスクIPL付き）またはHDD起動イメージから抽出する場合は、コアの開始位置は512バイト目です。

```sh
mkdir -p external/system
dd if=old_boot_2d.raw of=external/system/cpm86_core.bin bs=1 skip=512 count=9472 status=none
```

D88や2HD RAWでは配置が異なるため、上記の抽出コマンドはそのまま使用しないでください。

## コマンドの収録

起動イメージに収録したいCP/M-86用のCMDファイルやソースファイルを `external/commands/` に置いてください。標準コマンド（STAT.CMD、PIP.CMDなど）は別途用意します。

ファイル名はCP/Mの8.3形式とし、イメージ作成時に大文字へ変換され、ユーザー番号0に収録されます。ファイルの内容は変換されません。

付属のFORMAT.CMDなどを作成する場合は [command/README.md](command/README.md) を参照してください。

## 起動用FDイメージの作成

```sh
make boot-2d
make boot-2hd
```

各ターゲットは対応するD88とRAWを同時に生成します。片方だけ削除した場合も再生成されます。

生成されるファイル：

| メディア | D88 | RAW |
|---|---|---|
| 2D | build/fm11_cpm86_2d.d88 | build/fm11_cpm86_2d.raw |
| 2HD | build/fm11_cpm86_2hd.d88 | build/fm11_cpm86_2hd.raw |

2Dは40シリンダ、2ヘッド、16セクタ／トラック、256バイト／セクタ（320 KiB）です。2HDは77シリンダ、2ヘッド、26セクタ／トラックで、先頭の面トラックのみ128バイトFM、その他は256バイトMFMです。2HDのRAWは各物理セクタのデータをパディングなしで連結した1,021,696バイトの形式です。cpmtoolsでは付属のdiskdefs（offset 23296）を使用してください。旧256バイトスロット形式のRAWとは互換性がないため、旧イメージはD88から再変換するか、必要なファイルを退避してから再生成してください。起動用にはセクタ情報を保持するD88を推奨します。

`make` 単独では起動ディスクは生成されません。

## 起動用HDDイメージの作成

```sh
make boot-hdd HDD_MODEL=m2233b
```

生成されるファイル：

- `build/fm11_cpm86_boot_hdd.img` — HDD全体のRAWイメージ
- `build/ipl_hdd.bin` — HDDディスク先頭に書き込むIPL（512バイト）
- `build/cbios_hdd.bin` — HDD起動用CBIOS

HDD_MODELには次のモデルを指定できます（既定値はm2233b）。

| モデル | シリンダ | ヘッド |
|---|---:|---:|
| m2230b | 315 | 2 |
| m2231b | 157 | 4 |
| m2232b | 157 | 6 |
| m2233b | 315 | 4 |
| m2234b | 315 | 6 |
| m2235b | 315 | 8 |
| m2241b | 747 | 4 |
| m2242b | 747 | 7 |
| m2243b | 747 | 11 |

いずれも32セクタ／トラック、256バイト／セクタです。

**make boot-hddは実行するたびにHDDイメージを再生成します。** 利用中のディスクイメージはbuildディレクトリの外にコピーして使用してください。FDイメージも同様に、イメージ再作成でデータを失わないようにしてください。

## FM-11エミュレータでの起動

[FM-11エミュレータ](https://github.com/sueyasu/fm11-emulator)の8088 CPUカードを有効にし、使用するROMおよびRAM容量を通常の手順で設定してください。設定ファイルの例：

```ini
[main]
active = 8088

[main_8088]
installed = true
cpu = 8088
clock_hz = 8000000

[optional_cpu]
type = none

[memory]
ram_kib = 512
```

既存の動作するエミュレータ設定に、起動メディアに応じて次の設定を追加・変更します。パスは実際のファイルに置き換えてください。

2D起動：

```ini
[floppy_2d]
drive0 = /path/to/fm11_cpm86_2d.d88
```

2HD起動：

```ini
[DIPSW]
2HD_FDD = true

[floppy_2hd]
drive0 = /path/to/fm11_cpm86_2hd.d88
```

2D／2HDでは、使用するFDDに対応する元の8088フロッピーブートROMを用いて起動します。

HDD起動：

```ini
[hdd]
image = /path/to/fm11_cpm86_boot_hdd.img
```

HDD起動にも富士通標準の8088ブートROMを使用します。設定済みの標準ROMは変更せず、専用ROMの`--8088-rom`指定を加えずに起動してください。エミュレータでHDD起動を選択するため、`[DIPSW]`の`HDD = true`など、使用している設定に合ったブート機器設定も必要です。

```sh
fm11-sdl --config /path/to/fm11emu.conf
```

標準ROMからこのCP/M-86 HDD IPLへの引き渡しは、CP/M-80版の実績とIPLのソース構造から互換性を見込んでいますが、CP/M-86版での実行確認はまだ必要です。

画面用ROMなどは既存設定に従います。ローカルコンソール版では、起動のためにシリアル端末でキーを入力する必要はありません。

シリアル端末を利用する場合、エミュレータが表示するSerial PTYのパスに端末ソフトウェアを接続してください（例：`screen /dev/pts/5`）。

## シリアル端末を初期コンソールとするビルド

通常はローカル画面が初期コンソールです。起動時からシリアル端末を使用する場合は、次のようにビルドできます。

```sh
make clean
make NASM='nasm -DCONSOLE_LOCAL=0' boot-2d boot-2hd boot-hdd
```

専用HDDブートROMのシリアル版と、そのキー入力待ちは廃止しました。起動前の動作は標準ROMの仕様に従います。コンパイル条件の切り替え時はmake cleanを行ってください。buildディレクトリ内の既存イメージは削除されます。

## ファイルの追加・削除と再生成

external/commandsのファイルを追加・削除した後は、必要に応じてmake -Bでイメージを再作成します。

```sh
make -B boot-2d
make -B boot-2hd
```

既存のイメージ上で作成したファイルは再生成時に引き継がれません。
