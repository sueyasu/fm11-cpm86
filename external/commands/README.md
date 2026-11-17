# External CP/M-86 disk files

Place any CP/M-compatible 8.3-named regular files here:
`FDFORMAT.A86`, `FDIPL2D.INC`, `FDIPL2HD.INC`,
`PIP.CMD`, `NOTES.TXT`, and so on.

All files except this host-only `README.md` are automatically added
to both the 2D and 2HD images by `make boot-d88` or `make boot-2hd`.
They are stored byte-for-byte as CP/M files; text is not converted,
so an ASM86 source should already have CRLF and Ctrl-Z if required.

Only standard CP/M 8.3 names and characters are supported. File names
are converted to uppercase, and duplicate names (case-insensitive),
disk-capacity and directory-capacity errors abort image generation.

Use `make -B boot-d88` or `make -B boot-2hd` after **removing**
a file: Make cannot notice a disappeared wildcard prerequisite.
The supplied source code and tool binaries are external inputs and
are not tracked in this directory.
