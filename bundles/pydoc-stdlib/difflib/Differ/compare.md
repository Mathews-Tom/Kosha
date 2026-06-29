---
type: reference
title: "difflib.Differ.compare"
description: "Compare two sequences of lines; generate the resulting delta."
tags: ["difflib", "stdlib"]
---
# difflib.Differ.compare

Compare two sequences of lines; generate the resulting delta.

Each sequence must contain individual single-line strings ending with
newlines. Such sequences can be obtained from the `readlines()` method
of file-like objects.  The delta generated also consists of newline-
terminated strings, ready to be printed as-is via the writelines()
method of a file-like object.

Example:

>>> print(''.join(Differ().compare('one\ntwo\nthree\n'.splitlines(True),
...                                'ore\ntree\nemu\n'.splitlines(True))),
...       end="")
- one
?  ^
+ ore
?  ^
- two
- three
?  -
+ tree
+ emu

## Related

- [GenericAlias](/difflib/GenericAlias.md)
- [HtmlDiff](/difflib/HtmlDiff.md)
- [make_file](/difflib/HtmlDiff/make_file.md)
