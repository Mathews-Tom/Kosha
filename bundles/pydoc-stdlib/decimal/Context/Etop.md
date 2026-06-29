---
type: reference
title: "decimal.Context.Etop"
description: "Return a value equal to Emax - prec + 1. This is the maximum exponent"
tags: ["decimal", "stdlib"]
---
# decimal.Context.Etop

Return a value equal to Emax - prec + 1.  This is the maximum exponent
if the _clamp field of the context is set to 1 (IEEE clamp mode).  Etop()
must not be negative.

## Related

- [create_decimal](/decimal/Context/create_decimal.md)
- [create_decimal_from_float](/decimal/Context/create_decimal_from_float.md)
- [minus](/decimal/Context/minus.md)
