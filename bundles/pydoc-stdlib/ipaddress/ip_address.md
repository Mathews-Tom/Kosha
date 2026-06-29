---
type: reference
title: "ipaddress.ip_address"
description: "Take an IP string/int and return an object of the correct type."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.ip_address

Take an IP string/int and return an object of the correct type.

Args:
    address: A string or integer, the IP address.  Either IPv4 or
      IPv6 addresses may be supplied; integers less than 2**32 will
      be considered to be IPv4 by default.

Returns:
    An IPv4Address or IPv6Address object.

Raises:
    ValueError: if the *address* passed isn't either a v4 or a v6
      address

## Related

- [ip_interface](/ipaddress/ip_interface.md)
- [IPv4Network](/ipaddress/IPv4Network.md)
- [address_exclude](/ipaddress/IPv4Network/address_exclude.md)
