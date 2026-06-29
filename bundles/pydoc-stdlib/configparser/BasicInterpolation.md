---
type: reference
title: "configparser.BasicInterpolation"
description: "Interpolation as implemented in the classic ConfigParser."
tags: ["configparser", "stdlib"]
---
# configparser.BasicInterpolation

Interpolation as implemented in the classic ConfigParser.

The option values can contain format strings which refer to other values in
the same section, or values in the special default section.

For example:

    something: %(dir)s/whatever

would resolve the "%(dir)s" to the value of dir.  All reference
expansions are done late, on demand. If a user needs to use a bare % in
a configuration file, she can escape it by writing %%. Other % usage
is considered a user error and raises `InterpolationSyntaxError`.

## Related

- [ConverterMapping](/configparser/ConverterMapping.md)
- [pop](/configparser/ConverterMapping/pop.md)
- [popitem](/configparser/ConverterMapping/popitem.md)
