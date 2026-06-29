---
type: reference
title: "argparse.ArgumentParser.error"
description: "error(message: string)"
tags: ["argparse", "stdlib"]
---
# argparse.ArgumentParser.error

error(message: string)

Prints a usage message incorporating the message to stderr and
exits.

If you override this in a subclass, it should not return -- it
should either exit or raise an exception.

## Related

- [BooleanOptionalAction](/argparse/BooleanOptionalAction.md)
- [FileType](/argparse/FileType.md)
- [HelpFormatter](/argparse/HelpFormatter.md)
