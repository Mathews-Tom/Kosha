---
type: reference
title: "mimetypes.guess_type"
description: "Guess the type of a file based on its URL."
tags: ["mimetypes", "stdlib"]
---
# mimetypes.guess_type

Guess the type of a file based on its URL.

Return value is a tuple (type, encoding) where type is None if the
type can't be guessed (no or unknown suffix) or a string of the
form type/subtype, usable for a MIME Content-type header; and
encoding is None for no encoding or the name of the program used
to encode (e.g. compress or gzip).  The mappings are table
driven.  Encoding suffixes are case sensitive; type suffixes are
first tried case sensitive, then case insensitive.

The suffixes .tgz, .taz and .tz (case sensitive!) are all mapped
to ".tar.gz".  (This is table-driven too, using the dictionary
suffix_map).

Optional `strict' argument when false adds a bunch of commonly found, but
non-standard types.

## Related

- [MimeTypes](/mimetypes/MimeTypes.md)
- [add_type](/mimetypes/MimeTypes/add_type.md)
- [guess_all_extensions](/mimetypes/MimeTypes/guess_all_extensions.md)
