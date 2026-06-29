---
type: reference
title: "difflib.SequenceMatcher.find_longest_match"
description: "Find longest matching block in a[alo:ahi] and b[blo:bhi]."
tags: ["difflib", "stdlib"]
---
# difflib.SequenceMatcher.find_longest_match

Find longest matching block in a[alo:ahi] and b[blo:bhi].

By default it will find the longest match in the entirety of a and b.

If isjunk is not defined:

Return (i,j,k) such that a[i:i+k] is equal to b[j:j+k], where
    alo <= i <= i+k <= ahi
    blo <= j <= j+k <= bhi
and for all (i',j',k') meeting those conditions,
    k >= k'
    i <= i'
    and if i == i', j <= j'

In other words, of all maximal matching blocks, return one that
starts earliest in a, and of all those maximal matching blocks that
start earliest in a, return the one that starts earliest in b.

>>> s = SequenceMatcher(None, " abcd", "abcd abcd")
>>> s.find_longest_match(0, 5, 0, 9)
Match(a=0, b=4, size=5)

If isjunk is defined, first the longest matching block is
determined as above, but with the additional restriction that no
junk element appears in the block.  Then that block is extended as
far as possible by matching (only) junk elements on both sides.  So
the resulting block never matches on junk except as identical junk
happens to be adjacent to an "interesting" match.

Here's the same example as before, but considering blanks to be
junk.  That prevents " abcd" from matching the " abcd" at the tail
end of the second sequence directly.  Instead only the "abcd" can
match, and matches the leftmost "abcd" in the second sequence:

>>> s = SequenceMatcher(lambda x: x==" ", " abcd", "abcd abcd")
>>> s.find_longest_match(0, 5, 0, 9)
Match(a=1, b=0, size=4)

If no blocks match, return (alo, blo, 0).

>>> s = SequenceMatcher(None, "ab", "c")
>>> s.find_longest_match(0, 2, 0, 1)
Match(a=0, b=0, size=0)

## Related

- [get_grouped_opcodes](/difflib/SequenceMatcher/get_grouped_opcodes.md)
- [get_matching_blocks](/difflib/SequenceMatcher/get_matching_blocks.md)
- [get_opcodes](/difflib/SequenceMatcher/get_opcodes.md)
