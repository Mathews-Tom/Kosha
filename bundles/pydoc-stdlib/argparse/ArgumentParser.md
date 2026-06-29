---
type: reference
title: "argparse.ArgumentParser"
description: "Object for parsing command line strings into Python objects."
tags: ["argparse", "stdlib"]
---
# argparse.ArgumentParser

Object for parsing command line strings into Python objects.

Keyword Arguments:
    - prog -- The name of the program (default:
        ``os.path.basename(sys.argv[0])``)
    - usage -- A usage message (default: auto-generated from arguments)
    - description -- A description of what the program does
    - epilog -- Text following the argument descriptions
    - parents -- Parsers whose arguments should be copied into this one
    - formatter_class -- HelpFormatter class for printing help messages
    - prefix_chars -- Characters that prefix optional arguments
    - fromfile_prefix_chars -- Characters that prefix files containing
        additional arguments
    - argument_default -- The default value for all arguments
    - conflict_handler -- String indicating how to handle conflicts
    - add_help -- Add a -h/-help option
    - allow_abbrev -- Allow long options to be abbreviated unambiguously
    - exit_on_error -- Determines whether or not ArgumentParser exits with
        error info when an error occurs

## Related

- [add_argument](/argparse/ArgumentParser/add_argument.md)
- [error](/argparse/ArgumentParser/error.md)
- [BooleanOptionalAction](/argparse/BooleanOptionalAction.md)
