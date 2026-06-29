---
type: reference
title: "decimal.Context"
description: "The context affects almost all operations and controls rounding,"
tags: ["decimal", "stdlib"]
---
# decimal.Context

The context affects almost all operations and controls rounding,
Over/Underflow, raising of exceptions and much more.  A new context
can be constructed as follows:

    >>> c = Context(prec=28, Emin=-425000000, Emax=425000000,
    ...             rounding=ROUND_HALF_EVEN, capitals=1, clamp=1,
    ...             traps=[InvalidOperation, DivisionByZero, Overflow],
    ...             flags=[])
    >>>

## Related

- [Etiny](/decimal/Context/Etiny.md)
- [Etop](/decimal/Context/Etop.md)
- [create_decimal](/decimal/Context/create_decimal.md)
