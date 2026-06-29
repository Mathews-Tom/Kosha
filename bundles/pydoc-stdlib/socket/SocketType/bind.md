---
type: reference
title: "socket.SocketType.bind"
description: "bind(address)"
tags: ["socket", "stdlib"]
---
# socket.SocketType.bind

bind(address)

Bind the socket to a local address.  For IP sockets, the address is a
pair (host, port); the host must refer to the local host. For raw packet
sockets the address is a tuple (ifname, proto [,pkttype [,hatype [,addr]]])

## Related

- [connect](/socket/SocketType/connect.md)
- [CMSG_LEN](/socket/CMSG_LEN.md)
- [CMSG_SPACE](/socket/CMSG_SPACE.md)
