---
type: reference
title: "ipaddress.IPv6Network.address_exclude"
description: "Remove an address from a larger block."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.IPv6Network.address_exclude

Remove an address from a larger block.

For example:

    addr1 = ip_network('192.0.2.0/28')
    addr2 = ip_network('192.0.2.1/32')
    list(addr1.address_exclude(addr2)) =
        [IPv4Network('192.0.2.0/32'), IPv4Network('192.0.2.2/31'),
         IPv4Network('192.0.2.4/30'), IPv4Network('192.0.2.8/29')]

or IPv6:

    addr1 = ip_network('2001:db8::1/32')
    addr2 = ip_network('2001:db8::1/128')
    list(addr1.address_exclude(addr2)) =
        [ip_network('2001:db8::1/128'),
         ip_network('2001:db8::2/127'),
         ip_network('2001:db8::4/126'),
         ip_network('2001:db8::8/125'),
         ...
         ip_network('2001:db8:8000::/33')]

Args:
    other: An IPv4Network or IPv6Network object of the same type.

Returns:
    An iterator of the IPv(4|6)Network objects which is self
    minus other.

Raises:
    TypeError: If self and other are of differing address
      versions, or if other is not a network object.
    ValueError: If other is not completely contained by self.

## Related

- [compare_networks](/ipaddress/IPv6Network/compare_networks.md)
- [hosts](/ipaddress/IPv6Network/hosts.md)
- [subnets](/ipaddress/IPv6Network/subnets.md)
