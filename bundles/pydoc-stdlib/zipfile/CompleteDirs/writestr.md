---
type: reference
title: "zipfile.CompleteDirs.writestr"
description: "Write a file into the archive. The contents is 'data', which"
tags: ["zipfile", "stdlib"]
---
# zipfile.CompleteDirs.writestr

Write a file into the archive.  The contents is 'data', which
may be either a 'str' or a 'bytes' instance; if it is a 'str',
it is encoded as UTF-8 first.
'zinfo_or_arcname' is either a ZipInfo instance or
the name of the file in the archive.

## Related

- [LargeZipFile](/zipfile/LargeZipFile.md)
- [Path](/zipfile/Path.md)
- [open](/zipfile/Path/open.md)
