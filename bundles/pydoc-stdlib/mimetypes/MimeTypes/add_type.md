---
type: reference
title: "mimetypes.MimeTypes.add_type"
description: "Add a mapping between a type and an extension."
tags: ["mimetypes", "stdlib"]
---
# mimetypes.MimeTypes.add_type

Add a mapping between a type and an extension.

When the extension is already known, the new
type will replace the old one. When the type
is already known the extension will be added
to the list of known extensions.

If strict is true, information will be added to
list of standard types, else to the list of non-standard
types.

## Related

- [guess_all_extensions](/mimetypes/MimeTypes/guess_all_extensions.md)
- [guess_extension](/mimetypes/MimeTypes/guess_extension.md)
- [guess_type](/mimetypes/MimeTypes/guess_type.md)
