---
type: reference
title: "gzip.GzipFile.seek"
description: "Change the stream position to the given byte offset."
tags: ["gzip", "stdlib"]
---
# gzip.GzipFile.seek

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

- [seekable](/gzip/GzipFile/seekable.md)
- [truncate](/gzip/GzipFile/truncate.md)
- [writable](/gzip/GzipFile/writable.md)
