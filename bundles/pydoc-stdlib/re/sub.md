---
type: reference
title: "re.sub"
description: "Return the string obtained by replacing the leftmost"
tags: ["re", "stdlib"]
---
# re.sub

Return the string obtained by replacing the leftmost
non-overlapping occurrences of the pattern in string by the
replacement repl.  repl can be either a string or a callable;
if a string, backslash escapes in it are processed.  If it is
a callable, it's passed the Match object and must return
a replacement string to be used.

## Related

- [subn](/re/subn.md)
- [Match](/re/Match.md)
- [expand](/re/Match/expand.md)
