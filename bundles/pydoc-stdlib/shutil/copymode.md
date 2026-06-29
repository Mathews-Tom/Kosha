---
type: reference
title: "shutil.copymode"
description: "Copy mode bits from src to dst."
tags: ["shutil", "stdlib"]
---
# shutil.copymode

Copy mode bits from src to dst.

If follow_symlinks is not set, symlinks aren't followed if and only
if both `src` and `dst` are symlinks.  If `lchmod` isn't available
(e.g. Linux) this method does nothing.

## Related

- [copystat](/shutil/copystat.md)
- [copytree](/shutil/copytree.md)
- [disk_usage](/shutil/disk_usage.md)
