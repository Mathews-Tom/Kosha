---
type: reference
title: "difflib.IS_LINE_JUNK"
description: "Return True for ignorable line: iff `line` is blank or contains a single '#'."
tags: ["difflib", "stdlib"]
---
# difflib.IS_LINE_JUNK

Return True for ignorable line: iff `line` is blank or contains a single '#'.

Examples:

>>> IS_LINE_JUNK('\n')
True
>>> IS_LINE_JUNK('  #   \n')
True
>>> IS_LINE_JUNK('hello\n')
False

## Related

- [SequenceMatcher](/difflib/SequenceMatcher.md)
- [find_longest_match](/difflib/SequenceMatcher/find_longest_match.md)
- [get_grouped_opcodes](/difflib/SequenceMatcher/get_grouped_opcodes.md)
