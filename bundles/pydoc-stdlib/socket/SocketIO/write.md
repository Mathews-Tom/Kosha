---
type: reference
title: "socket.SocketIO.write"
description: "Write the given bytes or bytearray object *b* to the socket"
tags: ["socket", "stdlib"]
---
# socket.SocketIO.write

Write the given bytes or bytearray object *b* to the socket
and return the number of bytes written.  This can be less than
len(b) if not all data could be written.  If the socket is
non-blocking and no bytes could be written None is returned.

## Related

- [writelines](/socket/SocketIO/writelines.md)
- [SocketType](/socket/SocketType.md)
- [bind](/socket/SocketType/bind.md)
