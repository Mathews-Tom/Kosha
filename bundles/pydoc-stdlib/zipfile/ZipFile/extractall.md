---
type: reference
title: "zipfile.ZipFile.extractall"
description: "Extract all members from the archive to the current working"
tags: ["zipfile", "stdlib"]
---
# zipfile.ZipFile.extractall

Extract all members from the archive to the current working
directory. `path' specifies a different directory to extract to.
`members' is optional and must be a subset of the list returned
by namelist(). You can specify the password to decrypt all files
using 'pwd'.

## Related

- [open](/zipfile/ZipFile/open.md)
- [testzip](/zipfile/ZipFile/testzip.md)
- [CompleteDirs](/zipfile/CompleteDirs.md)
