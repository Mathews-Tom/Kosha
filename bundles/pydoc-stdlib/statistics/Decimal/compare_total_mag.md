---
type: reference
title: "statistics.Decimal.compare_total_mag"
description: "Compare two operands using their abstract representation rather than their"
tags: ["statistics", "stdlib"]
---
# statistics.Decimal.compare_total_mag

Compare two operands using their abstract representation rather than their
value as in compare_total(), but ignoring the sign of each operand.

x.compare_total_mag(y) is equivalent to x.copy_abs().compare_total(y.copy_abs()).

This operation is unaffected by context and is quiet: no flags are changed
and no rounding is performed. As an exception, the C version may raise
InvalidOperation if the second operand cannot be converted exactly.

## Related

- [copy_abs](/statistics/Decimal/copy_abs.md)
- [copy_negate](/statistics/Decimal/copy_negate.md)
- [Counter](/statistics/Counter.md)
