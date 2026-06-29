---
type: reference
title: "fnmatch.fnmatch"
description: "Test whether FILENAME matches PATTERN."
tags: ["fnmatch", "stdlib"]
---
# fnmatch.fnmatch

Test whether FILENAME matches PATTERN.

Patterns are Unix shell style:

*       matches everything
?       matches any single character
[seq]   matches any character in seq
[!seq]  matches any char not in seq

An initial period in FILENAME is not special.
Both FILENAME and PATTERN are first case-normalized
if the operating system requires it.
If you don't want this, use fnmatchcase(FILENAME, PATTERN).

## Related

- [fnmatchcase](/fnmatch/fnmatchcase.md)
- [translate](/fnmatch/translate.md)
