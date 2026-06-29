---
type: reference
title: "mimetypes.MimeTypes.guess_all_extensions"
description: "Guess the extensions for a file based on its MIME type."
tags: ["mimetypes", "stdlib"]
---
# mimetypes.MimeTypes.guess_all_extensions

Guess the extensions for a file based on its MIME type.

Return value is a list of strings giving the possible filename
extensions, including the leading dot ('.').  The extension is not
guaranteed to have been associated with any particular data stream,
but would be mapped to the MIME type `type' by guess_type().

Optional `strict' argument when false adds a bunch of commonly found,
but non-standard types.

## Related

- [guess_extension](/mimetypes/MimeTypes/guess_extension.md)
- [guess_type](/mimetypes/MimeTypes/guess_type.md)
- [read](/mimetypes/MimeTypes/read.md)
