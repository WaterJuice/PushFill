cmake_minimum_required(VERSION 3.6.0)

project( PushFill )

add_executable( PushFill
    Source/PushFill.c
    Source/WjCryptLib_Rc4.c
    Source/WjCryptLib_Rc4.h)

install(TARGETS PushFill DESTINATION .)

