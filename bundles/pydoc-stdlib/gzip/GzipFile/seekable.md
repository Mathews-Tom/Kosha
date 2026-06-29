---
type: reference
title: "gzip.GzipFile.seekable"
description: "Return whether object supports random access."
tags: ["gzip", "stdlib"]
---
# gzip.GzipFile.seekable

Return whether object supports random access.

If False, seek(), tell() and truncate() will raise OSError.
This method may need to do a test seek().

## Related

- [truncate](/gzip/GzipFile/truncate.md)
- [writable](/gzip/GzipFile/writable.md)
- [GzipFile](/gzip/GzipFile.md)
