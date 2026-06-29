---
type: reference
title: "ipaddress.IPv6Network"
description: "This class represents and manipulates 128-bit IPv6 networks."
tags: ["ipaddress", "stdlib"]
---
# ipaddress.IPv6Network

This class represents and manipulates 128-bit IPv6 networks.

Attributes: [examples for IPv6('2001:db8::1000/124')]
    .network_address: IPv6Address('2001:db8::1000')
    .hostmask: IPv6Address('::f')
    .broadcast_address: IPv6Address('2001:db8::100f')
    .netmask: IPv6Address('ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff0')
    .prefixlen: 124

## Related

- [address_exclude](/ipaddress/IPv6Network/address_exclude.md)
- [compare_networks](/ipaddress/IPv6Network/compare_networks.md)
- [hosts](/ipaddress/IPv6Network/hosts.md)
