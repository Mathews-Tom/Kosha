---
type: reference
title: "zipfile.CompleteDirs"
description: "A ZipFile subclass that ensures that implied directories"
tags: ["zipfile", "stdlib"]
---
# zipfile.CompleteDirs

A ZipFile subclass that ensures that implied directories
are always included in the namelist.

>>> list(CompleteDirs._implied_dirs(['foo/bar.txt', 'foo/bar/baz.txt']))
['foo/', 'foo/bar/']
>>> list(CompleteDirs._implied_dirs(['foo/bar.txt', 'foo/bar/baz.txt', 'foo/bar/']))
['foo/']

## Related

- [extract](/zipfile/CompleteDirs/extract.md)
- [extractall](/zipfile/CompleteDirs/extractall.md)
- [make](/zipfile/CompleteDirs/make.md)
