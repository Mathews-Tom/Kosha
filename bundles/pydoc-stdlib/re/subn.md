---
type: reference
title: "re.subn"
description: "Return a 2-tuple containing (new_string, number)."
tags: ["re", "stdlib"]
---
# re.subn

Return a 2-tuple containing (new_string, number).
new_string is the string obtained by replacing the leftmost
non-overlapping occurrences of the pattern in the source
string by the replacement repl.  number is the number of
substitutions that were made. repl can be either a string or a
callable; if a string, backslash escapes in it are processed.
If it is a callable, it's passed the Match object and must
return a replacement string to be used.

## Related

- [Match](/re/Match.md)
- [expand](/re/Match/expand.md)
- [group](/re/Match/group.md)
