---
type: reference
title: "os.chdir"
description: "Change the current working directory to the specified path."
tags: ["os", "stdlib"]
---
# os.chdir

Change the current working directory to the specified path.

path may always be specified as a string.
On some platforms, path may also be specified as an open file descriptor.
  If this functionality is unavailable, using it raises an exception.

## Related

- [chflags](/os/chflags.md)
- [chmod](/os/chmod.md)
- [chown](/os/chown.md)
