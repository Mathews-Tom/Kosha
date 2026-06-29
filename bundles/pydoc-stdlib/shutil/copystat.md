---
type: reference
title: "shutil.copystat"
description: "Copy file metadata"
tags: ["shutil", "stdlib"]
---
# shutil.copystat

Copy file metadata

Copy the permission bits, last access time, last modification time, and
flags from `src` to `dst`. On Linux, copystat() also copies the "extended
attributes" where possible. The file contents, owner, and group are
unaffected. `src` and `dst` are path-like objects or path names given as
strings.

If the optional flag `follow_symlinks` is not set, symlinks aren't
followed if and only if both `src` and `dst` are symlinks.

## Related

- [copytree](/shutil/copytree.md)
- [disk_usage](/shutil/disk_usage.md)
- [get_archive_formats](/shutil/get_archive_formats.md)
