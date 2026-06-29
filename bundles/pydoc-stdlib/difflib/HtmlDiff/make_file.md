---
type: reference
title: "difflib.HtmlDiff.make_file"
description: "Returns HTML file of side by side comparison with change highlights"
tags: ["difflib", "stdlib"]
---
# difflib.HtmlDiff.make_file

Returns HTML file of side by side comparison with change highlights

Arguments:
fromlines -- list of "from" lines
tolines -- list of "to" lines
fromdesc -- "from" file column header string
todesc -- "to" file column header string
context -- set to True for contextual differences (defaults to False
    which shows full differences).
numlines -- number of context lines.  When context is set True,
    controls number of lines displayed before and after the change.
    When context is False, controls the number of lines to place
    the "next" link anchors before the next change (so click of
    "next" link jumps to just before the change).
charset -- charset of the HTML document

## Related

- [make_table](/difflib/HtmlDiff/make_table.md)
- [IS_CHARACTER_JUNK](/difflib/IS_CHARACTER_JUNK.md)
- [IS_LINE_JUNK](/difflib/IS_LINE_JUNK.md)
