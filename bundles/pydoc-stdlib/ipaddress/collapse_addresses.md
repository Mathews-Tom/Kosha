---
type: reference
title: "ipaddress.collapse_addresses"
description: "Collapse a list of IP objects."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.collapse_addresses

Collapse a list of IP objects.

Example:
    collapse_addresses([IPv4Network('192.0.2.0/25'),
                        IPv4Network('192.0.2.128/25')]) ->
                       [IPv4Network('192.0.2.0/24')]

Args:
    addresses: An iterable of IPv4Network or IPv6Network objects.

Returns:
    An iterator of the collapsed IPv(4|6)Network objects.

Raises:
    TypeError: If passed a list of mixed version objects.

## Related

- [get_mixed_type_key](/ipaddress/get_mixed_type_key.md)
- [ip_address](/ipaddress/ip_address.md)
- [ip_interface](/ipaddress/ip_interface.md)
