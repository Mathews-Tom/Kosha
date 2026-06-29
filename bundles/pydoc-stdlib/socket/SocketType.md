---
type: reference
title: "socket.SocketType"
description: "socket(family=AF_INET, type=SOCK_STREAM, proto=0) -> socket object"
tags: ["socket", "stdlib"]
---
# socket.SocketType

socket(family=AF_INET, type=SOCK_STREAM, proto=0) -> socket object
socket(family=-1, type=-1, proto=-1, fileno=None) -> socket object

Open a socket of the given type.  The family argument specifies the
address family; it defaults to AF_INET.  The type argument specifies
whether this is a stream (SOCK_STREAM, this is the default)
or datagram (SOCK_DGRAM) socket.  The protocol argument defaults to 0,
specifying the default protocol.  Keyword arguments are accepted.
The socket is created as non-inheritable.

When a fileno is passed in, family, type and proto are auto-detected,
unless they are explicitly set.

A socket object represents one endpoint of a network connection.

Methods of socket objects (keyword arguments not allowed):

_accept() -- accept connection, returning new socket fd and client address
bind(addr) -- bind the socket to a local address
close() -- close the socket
connect(addr) -- connect the socket to a remote address
connect_ex(addr) -- connect, return an error code instead of an exception
dup() -- return a new socket fd duplicated from fileno()
fileno() -- return underlying file descriptor
getpeername() -- return remote address [*]
getsockname() -- return local address
getsockopt(level, optname[, buflen]) -- get socket options
gettimeout() -- return timeout or None
listen([n]) -- start listening for incoming connections
recv(buflen[, flags]) -- receive data
recv_into(buffer[, nbytes[, flags]]) -- receive data (into a buffer)
recvfrom(buflen[, flags]) -- receive data and sender's address
recvfrom_into(buffer[, nbytes, [, flags])
  -- receive data and sender's address (into a buffer)
sendall(data[, flags]) -- send all data
send(data[, flags]) -- send data, may not send all of it
sendto(data[, flags], addr) -- send data to a given address
setblocking(bool) -- set or clear the blocking I/O flag
getblocking() -- return True if socket is blocking, False if non-blocking
setsockopt(level, optname, value[, optlen]) -- set socket options
settimeout(None | float) -- set or clear the timeout
shutdown(how) -- shut down traffic in one or both directions

 [*] not available on all platforms!

## Related

- [bind](/socket/SocketType/bind.md)
- [connect](/socket/SocketType/connect.md)
- [CMSG_LEN](/socket/CMSG_LEN.md)
