---
type: reference
title: "ipaddress.get_mixed_type_key"
description: "Return a key suitable for sorting between networks and addresses."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.get_mixed_type_key

Return a key suitable for sorting between networks and addresses.

Address and Network objects are not sortable by default; they're
fundamentally different so the expression

    IPv4Address('192.0.2.0') <= IPv4Network('192.0.2.0/24')

doesn't make any sense.  There are some times however, where you may wish
to have ipaddress sort these for you anyway. If you need to do this, you
can use this function as the key= argument to sorted().

Args:
  obj: either a Network or Address object.
Returns:
  appropriate key.

## Related

- [ip_address](/ipaddress/ip_address.md)
- [ip_interface](/ipaddress/ip_interface.md)
- [IPv4Network](/ipaddress/IPv4Network.md)
