---
type: reference
title: "fractions.Decimal.fma"
description: "Fused multiply-add. Return self*other+third with no rounding of the"
tags: ["fractions", "stdlib"]
---
# fractions.Decimal.fma

Fused multiply-add.  Return self*other+third with no rounding of the
intermediate product self*other.

    >>> Decimal(2).fma(3, 5)
    Decimal('11')

## Related

- [from_float](/fractions/Decimal/from_float.md)
- [is_canonical](/fractions/Decimal/is_canonical.md)
- [is_finite](/fractions/Decimal/is_finite.md)
