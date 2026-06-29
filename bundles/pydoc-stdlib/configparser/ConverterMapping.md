---
type: reference
title: "configparser.ConverterMapping"
description: "Enables reuse of get*() methods between the parser and section proxies."
tags: ["configparser", "stdlib"]
---
# configparser.ConverterMapping

Enables reuse of get*() methods between the parser and section proxies.

If a parser class implements a getter directly, the value for the given
key will be ``None``. The presence of the converter name here enables
section proxies to find and use the implementation on the parser class.

## Related

- [pop](/configparser/ConverterMapping/pop.md)
- [popitem](/configparser/ConverterMapping/popitem.md)
- [update](/configparser/ConverterMapping/update.md)
