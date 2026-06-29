---
type: reference
title: "tokenize.TextIOWrapper.seek"
description: "Set the stream position, and return the new stream position."
tags: ["tokenize", "stdlib"]
---
# tokenize.TextIOWrapper.seek

Set the stream position, and return the new stream position.

  cookie
    Zero or an opaque number returned by tell().
  whence
    The relative position to seek from.

Four operations are supported, given by the following argument
combinations:

- seek(0, SEEK_SET): Rewind to the start of the stream.
- seek(cookie, SEEK_SET): Restore a previous position;
  'cookie' must be a number returned by tell().
- seek(0, SEEK_END): Fast-forward to the end of the stream.
- seek(0, SEEK_CUR): Leave the current stream position unchanged.

Any other argument combinations are invalid,
and may raise exceptions.

## Related

- [seekable](/tokenize/TextIOWrapper/seekable.md)
- [tell](/tokenize/TextIOWrapper/tell.md)
- [truncate](/tokenize/TextIOWrapper/truncate.md)
