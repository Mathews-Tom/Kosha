---
type: reference
title: "statistics.Decimal.compare"
description: "Compare self to other. Return a decimal value:"
tags: ["statistics", "stdlib"]
---
# statistics.Decimal.compare

Compare self to other.  Return a decimal value:

a or b is a NaN ==> Decimal('NaN')
a < b           ==> Decimal('-1')
a == b          ==> Decimal('0')
a > b           ==> Decimal('1')

## Related

- [compare_total](/statistics/Decimal/compare_total.md)
- [compare_total_mag](/statistics/Decimal/compare_total_mag.md)
- [copy_abs](/statistics/Decimal/copy_abs.md)
