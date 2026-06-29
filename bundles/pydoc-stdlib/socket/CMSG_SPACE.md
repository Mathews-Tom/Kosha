---
type: reference
title: "socket.CMSG_SPACE"
description: "CMSG_SPACE(length) -> buffer size"
tags: ["socket", "stdlib"]
---
# socket.CMSG_SPACE

CMSG_SPACE(length) -> buffer size

Return the buffer size needed for recvmsg() to receive an ancillary
data item with associated data of the given length, along with any
trailing padding.  The buffer space needed to receive multiple items
is the sum of the CMSG_SPACE() values for their associated data
lengths.  Raises OverflowError if length is outside the permissible
range of values.

## Related

- [SocketIO](/socket/SocketIO.md)
- [close](/socket/SocketIO/close.md)
- [flush](/socket/SocketIO/flush.md)
