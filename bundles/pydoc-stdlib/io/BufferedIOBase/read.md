---
type: reference
title: "io.BufferedIOBase.read"
description: "Read and return up to n bytes."
tags: ["io", "stdlib"]
---
# io.BufferedIOBase.read

Read and return up to n bytes.

If the size argument is omitted, None, or negative, read and
return all data until EOF.

If the size argument is positive, and the underlying raw stream is
not 'interactive', multiple raw reads may be issued to satisfy
the byte count (unless EOF is reached first).
However, for interactive raw streams (as well as sockets and pipes),
at most one raw read will be issued, and a short result does not
imply that EOF is imminent.

Return an empty bytes object on EOF.

Return None if the underlying raw stream was open in non-blocking
mode and no data is available at the moment.

## Related

- [read1](/io/BufferedIOBase/read1.md)
- [readable](/io/BufferedIOBase/readable.md)
- [readline](/io/BufferedIOBase/readline.md)
