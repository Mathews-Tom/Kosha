---
type: reference
title: "csv.StringIO.seek"
description: "Change stream position."
tags: ["csv", "stdlib"]
---
# csv.StringIO.seek

Change stream position.

Seek to character offset pos relative to position indicated by whence:
    0  Start of stream (the default).  pos should be >= 0;
    1  Current position - pos must be 0;
    2  End of stream - pos must be 0.
Returns the new absolute position.

## Related

- [truncate](/csv/StringIO/truncate.md)
- [write](/csv/StringIO/write.md)
- [writelines](/csv/StringIO/writelines.md)
