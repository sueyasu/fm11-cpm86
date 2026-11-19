# 付属コマンド

## FORMAT.CMD

FDおよびHDDをCP/M用に初期化するコマンドです。

| 指定例 | 動作 |
|---|---|
| FORMAT B: | 2D FDの物理・論理フォーマット |
| FORMAT F: /S | 2HD FDのフォーマットと起動用システムの書き込み |
| FORMAT B: /L | FDの低レベルフォーマットのみ |
| FORMAT I: | HDD全体の論理フォーマット |
| FORMAT HDD /S | HDD全体の論理フォーマットと起動用システムの書き込み |

A:～D:は2D、E:～H:は2HD、I:またはHDDはMDC HDDを指定します。HDDの/Lは使用できません。

/Sを利用する場合には、ディスクIPL付きの起動可能なシステムが入っているA:、E:またはI:をカレントドライブにしてください。FORMATは書き込み先を初期化する前に、カレントドライブからシステムを読み出します。独自IPL ROM専用の2D RAWイメージ（make boot-rom-2dで生成）は配置が異なるため、/Sのコピー元にはディスクIPL付きのシステムディスクを使用してください。

**対象ディスク上の既存ファイルは失われます。** 特にHDDでは区画単位ではなくディスク全体が対象になります。必要なデータは事前にバックアップしてください。

HDDの論理フォーマットは予約シリンダとディレクトリを初期化するもので、全データ領域の消去や物理フォーマットを行うものではありません。エミュレータでは、あらかじめ対応する容量のHDD RAWイメージを接続しておく必要があります。

### FORMAT.CMDの作成

Linux上でリポジトリのルートから次のコマンドを実行し、IPLのインクルードファイルを作成します。

```sh
make format-inc
```

次の4ファイルをCP/M-86上の同じドライブに転送します。

- command/FORMAT.A86
- command/FDIPL2D.INC
- command/FDIPL2HD.INC
- command/HDIPL.INC

CP/M-86上でASM86とGENCMDを使って作成します。

```text
A>ASM86 FORMAT.A86
A>GENCMD FORMAT
```

生成したFORMAT.CMDを使用してください。ASM86.CMDとGENCMD.CMDは別途用意する必要があります。

## ANSITEST.CMD

ローカル画面のANSI/VT100制御を確認するためのコマンドです。ディスクの内容を変更しません。

command/ANSITEST.A86をCP/M-86に転送し、次のように作成・実行します。

```text
A>ASM86 ANSITEST.A86
A>GENCMD ANSITEST
A>STAT CON:=CRT:
A>ANSITEST
```

9画面をキー入力で順に表示し、カーソル移動、消去、文字色・装飾などを確認できます。UC1:に設定すればシリアル端末への出力もあわせて確認できます。
