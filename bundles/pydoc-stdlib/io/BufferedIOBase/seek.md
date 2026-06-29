---
type: reference
title: "io.BufferedIOBase.seek"
description: "Change the stream position to the given byte offset."
tags: ["io", "stdlib"]
---
# io.BufferedIOBase.seek

Change the stream position to the given byte offset.

  offset
    The stream position, relative to 'whence'.
  whence
    The relative position to seek from.

The offset is interpreted relative to the position indicated by whence.
Values for whence are:

* os.SEEK_SET or 0 -- start of stream (the default); offset should be zero or positive
* os.SEEK_CUR or 1 -- current stream position; offset may be negative
* os.SEEK_END or 2 -- end of stream; offset is usually negative

Return the new absolute position.

## Related

- [seekable](/io/BufferedIOBase/seekable.md)
- [truncate](/io/BufferedIOBase/truncate.md)
- [writable](/io/BufferedIOBase/writable.md)
