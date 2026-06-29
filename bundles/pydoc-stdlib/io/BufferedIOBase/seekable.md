---
type: reference
title: "io.BufferedIOBase.seekable"
description: "Return whether object supports random access."
tags: ["io", "stdlib"]
---
# io.BufferedIOBase.seekable

Return whether object supports random access.

If False, seek(), tell() and truncate() will raise OSError.
This method may need to do a test seek().

## Related

- [truncate](/io/BufferedIOBase/truncate.md)
- [writable](/io/BufferedIOBase/writable.md)
- [write](/io/BufferedIOBase/write.md)
