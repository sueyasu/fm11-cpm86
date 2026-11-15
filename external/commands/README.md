# External CP/M-86 commands

Place your CP/M-86 `.CMD` programs here (e.g. `PIP.CMD`, `STAT.CMD`).
Files with `.CMD` or `.cmd` extensions are automatically included
in `build/fm11_cpm86_2d.img` by `make boot`.

Only valid CP/M 8.3 filenames are supported. The generated disk image
uses the native FM-11 2D format and is intended for the 8088 emulator
and compatible hardware. Command binaries are external inputs and are
not tracked here.

Run `make -B boot` to force a rebuild after removing a command file,
since Make does not otherwise track the disappearance of wildcard matches.
