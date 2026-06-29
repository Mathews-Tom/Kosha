---
type: reference
title: "difflib.SequenceMatcher.get_matching_blocks"
description: "Return list of triples describing matching subsequences."
tags: ["difflib", "stdlib"]
---
# difflib.SequenceMatcher.get_matching_blocks

Return list of triples describing matching subsequences.

Each triple is of the form (i, j, n), and means that
a[i:i+n] == b[j:j+n].  The triples are monotonically increasing in
i and in j.  New in Python 2.5, it's also guaranteed that if
(i, j, n) and (i', j', n') are adjacent triples in the list, and
the second is not the last triple in the list, then i+n != i' or
j+n != j'.  IOW, adjacent triples never describe adjacent equal
blocks.

The last triple is a dummy, (len(a), len(b), 0), and is the only
triple with n==0.

>>> s = SequenceMatcher(None, "abxcd", "abcd")
>>> list(s.get_matching_blocks())
[Match(a=0, b=0, size=2), Match(a=3, b=2, size=2), Match(a=5, b=4, size=0)]

## Related

- [get_opcodes](/difflib/SequenceMatcher/get_opcodes.md)
- [quick_ratio](/difflib/SequenceMatcher/quick_ratio.md)
- [ratio](/difflib/SequenceMatcher/ratio.md)
