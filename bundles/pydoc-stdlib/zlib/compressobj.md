---
type: reference
title: "zlib.compressobj"
description: "Return a compressor object."
tags: ["zlib", "stdlib"]
---
# zlib.compressobj

Return a compressor object.

level
  The compression level (an integer in the range 0-9 or -1; default is
  currently equivalent to 6).  Higher compression levels are slower,
  but produce smaller results.
method
  The compression algorithm.  If given, this must be DEFLATED.
wbits
  +9 to +15: The base-two logarithm of the window size.  Include a zlib
      container.
  -9 to -15: Generate a raw stream.
  +25 to +31: Include a gzip container.
memLevel
  Controls the amount of memory used for internal compression state.
  Valid values range from 1 to 9.  Higher values result in higher memory
  usage, faster compression, and smaller output.
strategy
  Used to tune the compression algorithm.  Possible values are
  Z_DEFAULT_STRATEGY, Z_FILTERED, and Z_HUFFMAN_ONLY.
zdict
  The predefined compression dictionary - a sequence of bytes
  containing subsequences that are likely to occur in the input data.

## Related

- [crc32](/zlib/crc32.md)
- [decompress](/zlib/decompress.md)
- [decompressobj](/zlib/decompressobj.md)
