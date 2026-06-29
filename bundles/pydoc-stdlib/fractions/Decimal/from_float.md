---
type: reference
title: "fractions.Decimal.from_float"
description: "Class method that converts a float to a decimal number, exactly."
tags: ["fractions", "stdlib"]
---
# fractions.Decimal.from_float

Class method that converts a float to a decimal number, exactly.
Since 0.1 is not exactly representable in binary floating point,
Decimal.from_float(0.1) is not the same as Decimal('0.1').

    >>> Decimal.from_float(0.1)
    Decimal('0.1000000000000000055511151231257827021181583404541015625')
    >>> Decimal.from_float(float('nan'))
    Decimal('NaN')
    >>> Decimal.from_float(float('inf'))
    Decimal('Infinity')
    >>> Decimal.from_float(float('-inf'))
    Decimal('-Infinity')

## Related

- [is_canonical](/fractions/Decimal/is_canonical.md)
- [is_finite](/fractions/Decimal/is_finite.md)
- [is_infinite](/fractions/Decimal/is_infinite.md)
