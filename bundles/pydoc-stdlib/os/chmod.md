---
type: reference
title: "os.chmod"
description: "Change the access permissions of a file."
tags: ["os", "stdlib"]
---
# os.chmod

Change the access permissions of a file.

  path
    Path to be modified.  May always be specified as a str, bytes, or a path-like object.
    On some platforms, path may also be specified as an open file descriptor.
    If this functionality is unavailable, using it raises an exception.
  mode
    Operating-system mode bitfield.
    Be careful when using number literals for *mode*. The conventional UNIX notation for
    numeric modes uses an octal base, which needs to be indicated with a ``0o`` prefix in
    Python.
  dir_fd
    If not None, it should be a file descriptor open to a directory,
    and path should be relative; path will then be relative to that
    directory.
  follow_symlinks
    If False, and the last element of the path is a symbolic link,
    chmod will modify the symbolic link itself instead of the file
    the link points to.

It is an error to use dir_fd or follow_symlinks when specifying path as
  an open file descriptor.
dir_fd and follow_symlinks may not be implemented on your platform.
  If they are unavailable, using them will raise a NotImplementedError.

## Related

- [chown](/os/chown.md)
- [cpu_count](/os/cpu_count.md)
- [device_encoding](/os/device_encoding.md)
