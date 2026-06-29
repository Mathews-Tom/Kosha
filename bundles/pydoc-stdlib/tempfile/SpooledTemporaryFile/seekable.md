---
type: reference
title: "tempfile.SpooledTemporaryFile.seekable"
description: "Return whether object supports random access."
tags: ["tempfile", "stdlib"]
---
# tempfile.SpooledTemporaryFile.seekable

Return whether object supports random access.

If False, seek(), tell() and truncate() will raise OSError.
This method may need to do a test seek().

## Related

- [truncate](/tempfile/SpooledTemporaryFile/truncate.md)
- [writable](/tempfile/SpooledTemporaryFile/writable.md)
- [writelines](/tempfile/SpooledTemporaryFile/writelines.md)
