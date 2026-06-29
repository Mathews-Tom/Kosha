---
type: reference
title: "typing.ABCMeta"
description: "Metaclass for defining Abstract Base Classes (ABCs)."
tags: ["typing", "stdlib"]
---
# typing.ABCMeta

Metaclass for defining Abstract Base Classes (ABCs).

Use this metaclass to create an ABC.  An ABC can be subclassed
directly, and then acts as a mix-in class.  You can also register
unrelated concrete classes (even built-in classes) and unrelated
ABCs as 'virtual subclasses' -- these and their descendants will
be considered subclasses of the registering ABC by the built-in
issubclass() function, but the registering ABC won't show up in
their MRO (Method Resolution Order) nor will method
implementations defined by the registering ABC be callable (not
even via super()).

## Related

- [register](/typing/ABCMeta/register.md)
- [Annotated](/typing/Annotated.md)
- [Any](/typing/Any.md)
