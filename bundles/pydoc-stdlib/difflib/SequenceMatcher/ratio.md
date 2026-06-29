---
type: reference
title: "difflib.SequenceMatcher.ratio"
description: "Return a measure of the sequences' similarity (float in [0,1])."
tags: ["difflib", "stdlib"]
---
# difflib.SequenceMatcher.ratio

Return a measure of the sequences' similarity (float in [0,1]).

Where T is the total number of elements in both sequences, and
M is the number of matches, this is 2.0*M / T.
Note that this is 1 if the sequences are identical, and 0 if
they have nothing in common.

.ratio() is expensive to compute if you haven't already computed
.get_matching_blocks() or .get_opcodes(), in which case you may
want to try .quick_ratio() or .real_quick_ratio() first to get an
upper bound.

>>> s = SequenceMatcher(None, "abcd", "bcde")
>>> s.ratio()
0.75
>>> s.quick_ratio()
0.75
>>> s.real_quick_ratio()
1.0

## Related

- [real_quick_ratio](/difflib/SequenceMatcher/real_quick_ratio.md)
- [Differ](/difflib/Differ.md)
- [compare](/difflib/Differ/compare.md)
