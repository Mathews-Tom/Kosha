---
type: reference
title: "mimetypes.MimeTypes.guess_type"
description: "Guess the type of a file which is either a URL or a path-like object."
tags: ["mimetypes", "stdlib"]
---
# mimetypes.MimeTypes.guess_type

Guess the type of a file which is either a URL or a path-like object.

Return value is a tuple (type, encoding) where type is None if
the type can't be guessed (no or unknown suffix) or a string
of the form type/subtype, usable for a MIME Content-type
header; and encoding is None for no encoding or the name of
the program used to encode (e.g. compress or gzip).  The
mappings are table driven.  Encoding suffixes are case
sensitive; type suffixes are first tried case sensitive, then
case insensitive.

The suffixes .tgz, .taz and .tz (case sensitive!) are all
mapped to '.tar.gz'.  (This is table-driven too, using the
dictionary suffix_map.)

Optional `strict' argument when False adds a bunch of commonly found,
but non-standard types.

## Related

- [read](/mimetypes/MimeTypes/read.md)
- [read_windows_registry](/mimetypes/MimeTypes/read_windows_registry.md)
- [readfp](/mimetypes/MimeTypes/readfp.md)
