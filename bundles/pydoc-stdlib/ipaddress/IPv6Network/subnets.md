---
type: reference
title: "ipaddress.IPv6Network.subnets"
description: "The subnets which join to make the current subnet."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.IPv6Network.subnets

The subnets which join to make the current subnet.

In the case that self contains only one IP
(self._prefixlen == 32 for IPv4 or self._prefixlen == 128
for IPv6), yield an iterator with just ourself.

Args:
    prefixlen_diff: An integer, the amount the prefix length
      should be increased by. This should not be set if
      new_prefix is also set.
    new_prefix: The desired new prefix length. This must be a
      larger number (smaller prefix) than the existing prefix.
      This should not be set if prefixlen_diff is also set.

Returns:
    An iterator of IPv(4|6) objects.

Raises:
    ValueError: The prefixlen_diff is too small or too large.
        OR
    prefixlen_diff and new_prefix are both set or new_prefix
      is a smaller number than the current prefix (smaller
      number means a larger network)

## Related

- [supernet](/ipaddress/IPv6Network/supernet.md)
- [collapse_addresses](/ipaddress/collapse_addresses.md)
- [get_mixed_type_key](/ipaddress/get_mixed_type_key.md)
