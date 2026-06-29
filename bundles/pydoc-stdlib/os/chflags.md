---
type: reference
title: "os.chflags"
description: "Set file flags."
tags: ["os", "stdlib"]
---
# os.chflags

Set file flags.

If follow_symlinks is False, and the last element of the path is a symbolic
  link, chflags will change flags on the symbolic link itself instead of the
  file the link points to.
follow_symlinks may not be implemented on your platform.  If it is
unavailable, using it will raise a NotImplementedError.

## Related

- [chmod](/os/chmod.md)
- [chown](/os/chown.md)
- [cpu_count](/os/cpu_count.md)
