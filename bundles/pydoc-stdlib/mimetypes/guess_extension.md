---
type: reference
title: "mimetypes.guess_extension"
description: "Guess the extension for a file based on its MIME type."
tags: ["mimetypes", "stdlib"]
---
# mimetypes.guess_extension

Guess the extension for a file based on its MIME type.

Return value is a string giving a filename extension, including the
leading dot ('.').  The extension is not guaranteed to have been
associated with any particular data stream, but would be mapped to the
MIME type `type' by guess_type().  If no extension can be guessed for
`type', None is returned.

Optional `strict' argument when false adds a bunch of commonly found,
but non-standard types.

## Related

- [guess_type](/mimetypes/guess_type.md)
- [MimeTypes](/mimetypes/MimeTypes.md)
- [add_type](/mimetypes/MimeTypes/add_type.md)
