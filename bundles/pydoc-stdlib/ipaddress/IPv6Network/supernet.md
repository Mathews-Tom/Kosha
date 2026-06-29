---
type: reference
title: "ipaddress.IPv6Network.supernet"
description: "The supernet containing the current network."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.IPv6Network.supernet

The supernet containing the current network.

Args:
    prefixlen_diff: An integer, the amount the prefix length of
      the network should be decreased by.  For example, given a
      /24 network and a prefixlen_diff of 3, a supernet with a
      /21 netmask is returned.

Returns:
    An IPv4 network object.

Raises:
    ValueError: If self.prefixlen - prefixlen_diff < 0. I.e., you have
      a negative prefix length.
        OR
    If prefixlen_diff and new_prefix are both set or new_prefix is a
      larger number than the current prefix (larger number means a
      smaller network)

## Related

- [collapse_addresses](/ipaddress/collapse_addresses.md)
- [get_mixed_type_key](/ipaddress/get_mixed_type_key.md)
- [ip_address](/ipaddress/ip_address.md)
