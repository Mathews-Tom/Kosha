---
type: reference
title: "pathlib.Path"
description: "PurePath subclass that can make system calls."
tags: ["pathlib", "stdlib"]
---
# pathlib.Path

PurePath subclass that can make system calls.

Path represents a filesystem path but unlike PurePath, also offers
methods to do system calls on path objects. Depending on your system,
instantiating a Path will return either a PosixPath or a WindowsPath
object. You can also instantiate a PosixPath or WindowsPath directly,
but cannot instantiate a WindowsPath on a POSIX system or vice versa.

## Related

- [absolute](/pathlib/Path/absolute.md)
- [exists](/pathlib/Path/exists.md)
- [expanduser](/pathlib/Path/expanduser.md)
