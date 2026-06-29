---
type: reference
title: "shutil.copy"
description: "Copy data and mode bits (\"cp src dst\"). Return the file's destination."
tags: ["shutil", "stdlib"]
---
# shutil.copy

Copy data and mode bits ("cp src dst"). Return the file's destination.

The destination may be a directory.

If follow_symlinks is false, symlinks won't be followed. This
resembles GNU's "cp -P src dst".

If source and destination are the same file, a SameFileError will be
raised.

## Related

- [copy2](/shutil/copy2.md)
- [copyfile](/shutil/copyfile.md)
- [copymode](/shutil/copymode.md)
