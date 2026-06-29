---
type: reference
title: "socket.SocketIO.readinto"
description: "Read up to len(b) bytes into the writable buffer *b* and return"
tags: ["socket", "stdlib"]
---
# socket.SocketIO.readinto

Read up to len(b) bytes into the writable buffer *b* and return
the number of bytes read.  If the socket is non-blocking and no bytes
are available, None is returned.

If *b* is non-empty, a 0 return value indicates that the connection
was shutdown at the other end.

## Related

- [readline](/socket/SocketIO/readline.md)
- [readlines](/socket/SocketIO/readlines.md)
- [seek](/socket/SocketIO/seek.md)
