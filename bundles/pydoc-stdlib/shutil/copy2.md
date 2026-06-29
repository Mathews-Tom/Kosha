---
type: reference
title: "shutil.copy2"
description: "Copy data and metadata. Return the file's destination."
tags: ["shutil", "stdlib"]
---
# shutil.copy2

Copy data and metadata. Return the file's destination.

Metadata is copied with copystat(). Please see the copystat function
for more information.

The destination may be a directory.

If follow_symlinks is false, symlinks won't be followed. This
resembles GNU's "cp -P src dst".

## Related

- [copyfile](/shutil/copyfile.md)
- [copymode](/shutil/copymode.md)
- [copystat](/shutil/copystat.md)
