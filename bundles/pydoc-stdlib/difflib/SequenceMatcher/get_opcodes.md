---
type: reference
title: "difflib.SequenceMatcher.get_opcodes"
description: "Return list of 5-tuples describing how to turn a into b."
tags: ["difflib", "stdlib"]
---
# difflib.SequenceMatcher.get_opcodes

Return list of 5-tuples describing how to turn a into b.

Each tuple is of the form (tag, i1, i2, j1, j2).  The first tuple
has i1 == j1 == 0, and remaining tuples have i1 == the i2 from the
tuple preceding it, and likewise for j1 == the previous j2.

The tags are strings, with these meanings:

'replace':  a[i1:i2] should be replaced by b[j1:j2]
'delete':   a[i1:i2] should be deleted.
            Note that j1==j2 in this case.
'insert':   b[j1:j2] should be inserted at a[i1:i1].
            Note that i1==i2 in this case.
'equal':    a[i1:i2] == b[j1:j2]

>>> a = "qabxcd"
>>> b = "abycdf"
>>> s = SequenceMatcher(None, a, b)
>>> for tag, i1, i2, j1, j2 in s.get_opcodes():
...    print(("%7s a[%d:%d] (%s) b[%d:%d] (%s)" %
...           (tag, i1, i2, a[i1:i2], j1, j2, b[j1:j2])))
 delete a[0:1] (q) b[0:0] ()
  equal a[1:3] (ab) b[0:2] (ab)
replace a[3:4] (x) b[2:3] (y)
  equal a[4:6] (cd) b[3:5] (cd)
 insert a[6:6] () b[5:6] (f)

## Related

- [quick_ratio](/difflib/SequenceMatcher/quick_ratio.md)
- [ratio](/difflib/SequenceMatcher/ratio.md)
- [real_quick_ratio](/difflib/SequenceMatcher/real_quick_ratio.md)
