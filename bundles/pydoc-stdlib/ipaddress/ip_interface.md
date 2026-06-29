---
type: reference
title: "ipaddress.ip_interface"
description: "Take an IP string/int and return an object of the correct type."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.ip_interface

Take an IP string/int and return an object of the correct type.

Args:
    address: A string or integer, the IP address.  Either IPv4 or
      IPv6 addresses may be supplied; integers less than 2**32 will
      be considered to be IPv4 by default.

Returns:
    An IPv4Interface or IPv6Interface object.

Raises:
    ValueError: if the string passed isn't either a v4 or a v6
      address.

Notes:
    The IPv?Interface classes describe an Address on a particular
    Network, so they're basically a combination of both the Address
    and Network classes.

## Related

- [IPv4Network](/ipaddress/IPv4Network.md)
- [address_exclude](/ipaddress/IPv4Network/address_exclude.md)
- [compare_networks](/ipaddress/IPv4Network/compare_networks.md)
