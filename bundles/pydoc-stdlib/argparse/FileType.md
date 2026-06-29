---
type: reference
title: "argparse.FileType"
description: "Factory for creating file object types"
tags: ["argparse", "stdlib"]
---
# argparse.FileType

Factory for creating file object types

Instances of FileType are typically passed as type= arguments to the
ArgumentParser add_argument() method.

Keyword Arguments:
    - mode -- A string indicating how the file is to be opened. Accepts the
        same values as the builtin open() function.
    - bufsize -- The file's desired buffer size. Accepts the same values as
        the builtin open() function.
    - encoding -- The file's encoding. Accepts the same values as the
        builtin open() function.
    - errors -- A string indicating how encoding and decoding errors are to
        be handled. Accepts the same value as the builtin open() function.

## Related

- [HelpFormatter](/argparse/HelpFormatter.md)
- [MetavarTypeHelpFormatter](/argparse/MetavarTypeHelpFormatter.md)
- [Namespace](/argparse/Namespace.md)
