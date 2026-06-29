---
type: reference
title: "shlex.StringIO.seek"
description: "Change stream position."
tags: ["shlex", "stdlib"]
---
# shlex.StringIO.seek

Change stream position.

Seek to character offset pos relative to position indicated by whence:
    0  Start of stream (the default).  pos should be >= 0;
    1  Current position - pos must be 0;
    2  End of stream - pos must be 0.
Returns the new absolute position.

## Related

- [truncate](/shlex/StringIO/truncate.md)
- [write](/shlex/StringIO/write.md)
- [writelines](/shlex/StringIO/writelines.md)
