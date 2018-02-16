PushFill
========

Push out old data off a disc by filling up a file with random-like data.

Syntax
    `PushFill <filename>`

This will create or append to a file called *filename*.

This program will fill a file with random-like data as fast as possible.
The file is written to in 10MByte blocks at a time. The first block of
a set of 256 blocks is generated from an RC4 stream. The following 255
blocks are the same as the first block with a counter value added to every
byte. This keeps the blocks different while keeping maximum speed. Generating
RC4 for every block is slower. After 256 blocks the RC4 stream is used again
to generate the next block.

The purpose of this program is to fill a disc up with data in a way that 
can not be optimised out by the underlying system. This ensures that the
device actually has to use all its blocks in order to store the data and
can not "cheat" by noticing blocks full of zero and simply setting a flag.

Because each block is different and based on an RC4 stream, a file system
can not compress the file to use less blocks than the size of the file.

For example, if you want to ensure a disc has no left over data on it, then
format it and then run PushFill on it until it is full. Then delete the
output file. As all blocks would have been used at this point you can be
fairly confident that there is no previous data that can be recovered.

*Created February 2018*


Caveats
-------

1)  A device may use wear-levelling and not expose all the physical blocks to
the operating system. Therefore some physical blocks may not be written to.
Additionally some blocks may be permanently marked as unusable and so will never
haev data written to them again.

2)  The operating system may contain some other snapshot-ing or backup of
the data.

3)  This will not fill up blocks that are used by the file system for other
purposes. For example on NTFS systems there could be deleted data left in the
MFT that is not touched by this program.

4)  The output of this program is not cryptographically strong. It is not
designed for that, it is designed for a quick way to "mostly" push out old
data off a disc. 


Building
--------

Build using cmake.

    cmake -H. -Bbuild -DCMAKE_INSTALL_PREFIX=bin
    cmake --build build --target install


License
=======

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>

