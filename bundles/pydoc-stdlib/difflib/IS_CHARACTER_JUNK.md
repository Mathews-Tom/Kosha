---
type: reference
title: "difflib.IS_CHARACTER_JUNK"
description: "Return True for ignorable character: iff `ch` is a space or tab."
tags: ["difflib", "stdlib"]
---
# difflib.IS_CHARACTER_JUNK

Return True for ignorable character: iff `ch` is a space or tab.

Examples:

>>> IS_CHARACTER_JUNK(' ')
True
>>> IS_CHARACTER_JUNK('\t')
True
>>> IS_CHARACTER_JUNK('\n')
False
>>> IS_CHARACTER_JUNK('x')
False

## Related

- [IS_LINE_JUNK](/difflib/IS_LINE_JUNK.md)
- [SequenceMatcher](/difflib/SequenceMatcher.md)
- [find_longest_match](/difflib/SequenceMatcher/find_longest_match.md)
