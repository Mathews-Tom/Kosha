---
type: reference
title: "io.BufferedIOBase"
description: "Base class for buffered IO objects."
tags: ["io", "stdlib"]
---
# io.BufferedIOBase

Base class for buffered IO objects.

The main difference with RawIOBase is that the read() method
supports omitting the size argument, and does not have a default
implementation that defers to readinto().

In addition, read(), readinto() and write() may raise
BlockingIOError if the underlying raw stream is in non-blocking
mode and not ready; unlike their raw counterparts, they will never
return None.

A typical implementation should not inherit from a RawIOBase
implementation, but wrap one.

## Related

- [close](/io/BufferedIOBase/close.md)
- [detach](/io/BufferedIOBase/detach.md)
- [fileno](/io/BufferedIOBase/fileno.md)
