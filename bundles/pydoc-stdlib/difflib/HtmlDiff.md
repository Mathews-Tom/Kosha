---
type: reference
title: "difflib.HtmlDiff"
description: "For producing HTML side by side comparison with change highlights."
tags: ["difflib", "stdlib"]
---
# difflib.HtmlDiff

For producing HTML side by side comparison with change highlights.

This class can be used to create an HTML table (or a complete HTML file
containing the table) showing a side by side, line by line comparison
of text with inter-line and intra-line change highlights.  The table can
be generated in either full or contextual difference mode.

The following methods are provided for HTML generation:

make_table -- generates HTML for a single side by side table
make_file -- generates complete HTML file with a single side by side table

See tools/scripts/diff.py for an example usage of this class.

## Related

- [make_file](/difflib/HtmlDiff/make_file.md)
- [make_table](/difflib/HtmlDiff/make_table.md)
- [IS_CHARACTER_JUNK](/difflib/IS_CHARACTER_JUNK.md)
