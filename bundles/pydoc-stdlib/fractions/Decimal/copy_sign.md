---
type: reference
title: "fractions.Decimal.copy_sign"
description: "Return a copy of the first operand with the sign set to be the same as the"
tags: ["fractions", "stdlib"]
---
# fractions.Decimal.copy_sign

Return a copy of the first operand with the sign set to be the same as the
sign of the second operand. For example:

    >>> Decimal('2.3').copy_sign(Decimal('-1.5'))
    Decimal('-2.3')

This operation is unaffected by context and is quiet: no flags are changed
and no rounding is performed. As an exception, the C version may raise
InvalidOperation if the second operand cannot be converted exactly.

## Related

- [exp](/fractions/Decimal/exp.md)
- [fma](/fractions/Decimal/fma.md)
- [from_float](/fractions/Decimal/from_float.md)
