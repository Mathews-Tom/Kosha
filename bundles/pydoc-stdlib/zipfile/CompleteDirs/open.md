---
type: reference
title: "zipfile.CompleteDirs.open"
description: "Return file-like object for 'name'."
tags: ["zipfile", "stdlib"]
---
# zipfile.CompleteDirs.open

Return file-like object for 'name'.

name is a string for the file name within the ZIP file, or a ZipInfo
object.

mode should be 'r' to read a file already in the ZIP file, or 'w' to
write to a file newly added to the archive.

pwd is the password to decrypt files (only used for reading).

When writing, if the file size is not known in advance but may exceed
2 GiB, pass force_zip64 to use the ZIP64 format, which can handle large
files.  If the size is known in advance, it is best to pass a ZipInfo
instance for name, with zinfo.file_size set.

## Related

- [resolve_dir](/zipfile/CompleteDirs/resolve_dir.md)
- [testzip](/zipfile/CompleteDirs/testzip.md)
- [writestr](/zipfile/CompleteDirs/writestr.md)
