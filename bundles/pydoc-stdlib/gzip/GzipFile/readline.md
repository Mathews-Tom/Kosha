---
type: reference
title: "gzip.GzipFile.readline"
description: "Read and return a line from the stream."
tags: ["gzip", "stdlib"]
---
# gzip.GzipFile.readline

Read and return a line from the stream.

If size is specified, at most size bytes will be read.

The line terminator is always b'\n' for binary files; for text
files, the newlines argument to open can be used to select the line
terminator(s) recognized.

## Related

- [readlines](/gzip/GzipFile/readlines.md)
- [rewind](/gzip/GzipFile/rewind.md)
- [seek](/gzip/GzipFile/seek.md)
