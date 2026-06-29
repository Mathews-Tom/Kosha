---
type: reference
title: "decimal.Decimal.compare"
description: "Compare self to other. Return a decimal value:"
tags: ["decimal", "stdlib"]
---
# decimal.Decimal.compare

Compare self to other.  Return a decimal value:

a or b is a NaN ==> Decimal('NaN')
a < b           ==> Decimal('-1')
a == b          ==> Decimal('0')
a > b           ==> Decimal('1')

## Related

- [compare_total](/decimal/Decimal/compare_total.md)
- [compare_total_mag](/decimal/Decimal/compare_total_mag.md)
- [Context](/decimal/Context.md)
