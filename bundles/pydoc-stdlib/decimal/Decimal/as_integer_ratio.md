---
type: reference
title: "decimal.Decimal.as_integer_ratio"
description: "Decimal.as_integer_ratio() -> (int, int)"
tags: ["decimal", "stdlib"]
---
# decimal.Decimal.as_integer_ratio

Decimal.as_integer_ratio() -> (int, int)

Return a pair of integers, whose ratio is exactly equal to the original
Decimal and with a positive denominator. The ratio is in lowest terms.
Raise OverflowError on infinities and a ValueError on NaNs.

## Related

- [canonical](/decimal/Decimal/canonical.md)
- [compare](/decimal/Decimal/compare.md)
- [compare_total](/decimal/Decimal/compare_total.md)
