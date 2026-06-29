---
type: reference
title: "difflib.SequenceMatcher"
description: "SequenceMatcher is a flexible class for comparing pairs of sequences of"
tags: ["difflib", "stdlib"]
---
# difflib.SequenceMatcher

SequenceMatcher is a flexible class for comparing pairs of sequences of
any type, so long as the sequence elements are hashable.  The basic
algorithm predates, and is a little fancier than, an algorithm
published in the late 1980's by Ratcliff and Obershelp under the
hyperbolic name "gestalt pattern matching".  The basic idea is to find
the longest contiguous matching subsequence that contains no "junk"
elements (R-O doesn't address junk).  The same idea is then applied
recursively to the pieces of the sequences to the left and to the right
of the matching subsequence.  This does not yield minimal edit
sequences, but does tend to yield matches that "look right" to people.

SequenceMatcher tries to compute a "human-friendly diff" between two
sequences.  Unlike e.g. UNIX(tm) diff, the fundamental notion is the
longest *contiguous* & junk-free matching subsequence.  That's what
catches peoples' eyes.  The Windows(tm) windiff has another interesting
notion, pairing up elements that appear uniquely in each sequence.
That, and the method here, appear to yield more intuitive difference
reports than does diff.  This method appears to be the least vulnerable
to syncing up on blocks of "junk lines", though (like blank lines in
ordinary text files, or maybe "<P>" lines in HTML files).  That may be
because this is the only method of the 3 that has a *concept* of
"junk" <wink>.

Example, comparing two strings, and considering blanks to be "junk":

>>> s = SequenceMatcher(lambda x: x == " ",
...                     "private Thread currentThread;",
...                     "private volatile Thread currentThread;")
>>>

.ratio() returns a float in [0, 1], measuring the "similarity" of the
sequences.  As a rule of thumb, a .ratio() value over 0.6 means the
sequences are close matches:

>>> print(round(s.ratio(), 3))
0.866
>>>

If you're only interested in where the sequences match,
.get_matching_blocks() is handy:

>>> for block in s.get_matching_blocks():
...     print("a[%d] and b[%d] match for %d elements" % block)
a[0] and b[0] match for 8 elements
a[8] and b[17] match for 21 elements
a[29] and b[38] match for 0 elements

Note that the last tuple returned by .get_matching_blocks() is always a
dummy, (len(a), len(b), 0), and this is the only case in which the last
tuple element (number of elements matched) is 0.

If you want to know how to change the first sequence into the second,
use .get_opcodes():

>>> for opcode in s.get_opcodes():
...     print("%6s a[%d:%d] b[%d:%d]" % opcode)
 equal a[0:8] b[0:8]
insert a[8:8] b[8:17]
 equal a[8:29] b[17:38]

See the Differ class for a fancy human-friendly file differencer, which
uses SequenceMatcher both to compare sequences of lines, and to compare
sequences of characters within similar (near-matching) lines.

See also function get_close_matches() in this module, which shows how
simple code building on SequenceMatcher can be used to do useful work.

Timing:  Basic R-O is cubic time worst case and quadratic time expected
case.  SequenceMatcher is quadratic time for the worst case and has
expected-case behavior dependent in a complicated way on how many
elements the sequences have in common; best case time is linear.

## Related

- [find_longest_match](/difflib/SequenceMatcher/find_longest_match.md)
- [get_grouped_opcodes](/difflib/SequenceMatcher/get_grouped_opcodes.md)
- [get_matching_blocks](/difflib/SequenceMatcher/get_matching_blocks.md)
