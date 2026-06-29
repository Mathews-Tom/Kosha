---
type: reference
title: "configparser.DuplicateSectionError"
description: "Raised when a section is repeated in an input source."
tags: ["configparser", "stdlib"]
---
# configparser.DuplicateSectionError

Raised when a section is repeated in an input source.

Possible repetitions that raise this exception are: multiple creation
using the API or in strict parsers when a section is found more than once
in a single input file, string or dictionary.

## Related

- [ExtendedInterpolation](/configparser/ExtendedInterpolation.md)
- [InterpolationSyntaxError](/configparser/InterpolationSyntaxError.md)
- [LegacyInterpolation](/configparser/LegacyInterpolation.md)
