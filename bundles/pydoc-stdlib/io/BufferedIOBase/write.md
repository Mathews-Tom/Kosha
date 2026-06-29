---
type: reference
title: "io.BufferedIOBase.write"
description: "Write buffer b to the IO stream."
tags: ["io", "stdlib"]
---
# io.BufferedIOBase.write

Write buffer b to the IO stream.

Return the number of bytes written, which is always
the length of b in bytes.

Raise BlockingIOError if the buffer is full and the
underlying raw stream cannot accept more data at the moment.

## Related

- [BufferedIOBase](/io/BufferedIOBase.md)
- [close](/io/BufferedIOBase/close.md)
- [detach](/io/BufferedIOBase/detach.md)
