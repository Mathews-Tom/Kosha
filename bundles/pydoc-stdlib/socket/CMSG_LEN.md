---
type: reference
title: "socket.CMSG_LEN"
description: "CMSG_LEN(length) -> control message length"
tags: ["socket", "stdlib"]
---
# socket.CMSG_LEN

CMSG_LEN(length) -> control message length

Return the total length, without trailing padding, of an ancillary
data item with associated data of the given length.  This value can
often be used as the buffer size for recvmsg() to receive a single
item of ancillary data, but RFC 3542 requires portable applications to
use CMSG_SPACE() and thus include space for padding, even when the
item will be the last in the buffer.  Raises OverflowError if length
is outside the permissible range of values.

## Related

- [CMSG_SPACE](/socket/CMSG_SPACE.md)
- [SocketIO](/socket/SocketIO.md)
- [close](/socket/SocketIO/close.md)
