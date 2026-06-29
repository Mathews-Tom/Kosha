---
type: reference
title: "os.chown"
description: "Change the owner and group id of path to the numeric uid and gid.\\"
tags: ["os", "stdlib"]
---
# os.chown

Change the owner and group id of path to the numeric uid and gid.\

  path
    Path to be examined; can be string, bytes, a path-like object, or open-file-descriptor int.
  dir_fd
    If not None, it should be a file descriptor open to a directory,
    and path should be relative; path will then be relative to that
    directory.
  follow_symlinks
    If False, and the last element of the path is a symbolic link,
    stat will examine the symbolic link itself instead of the file
    the link points to.

path may always be specified as a string.
On some platforms, path may also be specified as an open file descriptor.
  If this functionality is unavailable, using it raises an exception.
If dir_fd is not None, it should be a file descriptor open to a directory,
  and path should be relative; path will then be relative to that directory.
If follow_symlinks is False, and the last element of the path is a symbolic
  link, chown will modify the symbolic link itself instead of the file the
  link points to.
It is an error to use dir_fd or follow_symlinks when specifying path as
  an open file descriptor.
dir_fd and follow_symlinks may not be implemented on your platform.
  If they are unavailable, using them will raise a NotImplementedError.

## Related

- [cpu_count](/os/cpu_count.md)
- [device_encoding](/os/device_encoding.md)
- [execl](/os/execl.md)
