---
type: reference
title: "ipaddress.IPv4Network.compare_networks"
description: "Compare two IP objects."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.IPv4Network.compare_networks

Compare two IP objects.

This is only concerned about the comparison of the integer
representation of the network addresses.  This means that the
host bits aren't considered at all in this method.  If you want
to compare host bits, you can easily enough do a
'HostA._ip < HostB._ip'

Args:
    other: An IP object.

Returns:
    If the IP versions of self and other are the same, returns:

    -1 if self < other:
      eg: IPv4Network('192.0.2.0/25') < IPv4Network('192.0.2.128/25')
      IPv6Network('2001:db8::1000/124') <
          IPv6Network('2001:db8::2000/124')
    0 if self == other
      eg: IPv4Network('192.0.2.0/24') == IPv4Network('192.0.2.0/24')
      IPv6Network('2001:db8::1000/124') ==
          IPv6Network('2001:db8::1000/124')
    1 if self > other
      eg: IPv4Network('192.0.2.128/25') > IPv4Network('192.0.2.0/25')
          IPv6Network('2001:db8::2000/124') >
              IPv6Network('2001:db8::1000/124')

  Raises:
      TypeError if the IP versions are different.

## Related

- [hosts](/ipaddress/IPv4Network/hosts.md)
- [subnets](/ipaddress/IPv4Network/subnets.md)
- [supernet](/ipaddress/IPv4Network/supernet.md)
