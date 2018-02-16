////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  PushFill
//
//  Continuously writes to a file random-ish data designed to fill up the disc writing over every free block
//
//  This is free and unencumbered software released into the public domain - February 2018 waterjuice.org
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  IMPORTS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <sys/timeb.h>
#include "WjCryptLib_Rc4.h"

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  DEFINITIONS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#ifndef __min
   #define __min( x, y )  (((x) < (y))?(x):(y))
#endif

#if defined( _WIN32 )
    #define timeb _timeb
    #define ftime _ftime
#endif

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  CONSTANTS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#define FILL_BUFFER_SIZE                        ( 10 * 1024 * 1024 )        // 10 MBytes
#define MIN_MILLISECONDS_BETWEEN_DISPLAY        ( 2000 )                    // 2 seconds

#define VERSION_STR "1.0.0"

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  FUNCTIONS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  SeedStreamWithRandom
//
//  Initialises an RC4 stream with a random key
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
void
    SeedStreamWithRandom
    (
        Rc4Context*         Context                 // out
    )
{
    struct
    {
        struct timeb        time;
        void*               address;
        void*               address2;
    } seedValues;

    ftime( &seedValues.time );
    seedValues.address = Context;
    seedValues.address2 = (void*)SeedStreamWithRandom;

    Rc4Initialise( Context, &seedValues, sizeof(seedValues), 0 );
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  GetMilliSecondTime
//
//  Gets a 64bit number containing the number of milliseconds since 1-1-1970
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
uint64_t
    GetMilliSecondTime
    (
        void
    )
{
    struct timeb    timeValue = {0};
    uint64_t        milliseconds;

    ftime( &timeValue );
    milliseconds = ((uint64_t)timeValue.time) * 1000ULL;
    milliseconds += timeValue.millitm;

    return milliseconds;
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  DisplayFillRate
//
//  Display the fill rate in units such as MBps, or GBps etc
//  Rate input is in Bps.
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
void
    DisplayFillRate
    (
        double      Rate                // [in]
    )
{
    char const*     Prefixes[] = { "Bps", "kBps", "MBps", "GBps", "TBps" };
    uint32_t const  NumPrefixes = sizeof(Prefixes) / sizeof(Prefixes[0]);
    uint32_t        i;
    double          newRate;

    newRate = Rate;
    i = 0;
    while( 1 )
    {
        if( newRate < (1024.0)  ||  i >= NumPrefixes )
        {
            printf( "%6.1f %s", newRate, Prefixes[i] );
            break;
        }
        else
        {
            newRate = newRate / 1024.0;
            i += 1;
        }
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  DisplayDataAmount
//
//  Display the data amount in units such as MB or GB etc
//  TotalBytes input is in Bytes
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
void
    DisplayDataAmount
    (
        uint64_t        TotalBytes          // [in]
    )
{
    char const*     Prefixes[] = { "B", "kB", "MB", "GB", "TB" };
    uint32_t const  NumPrefixes = sizeof(Prefixes) / sizeof(Prefixes[0]);
    uint32_t        i;
    double          newTotal;

    newTotal = (double)TotalBytes;
    i = 0;
    while( 1 )
    {
        if( newTotal < (1024.0)  ||  i >= NumPrefixes )
        {
            printf( "%6.1f %s", newTotal, Prefixes[i] );
            break;
        }
        else
        {
            newTotal = newTotal / 1024.0;
            i += 1;
        }
    }
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  DisplayStats
//
//  Display stats to stdout
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
void
    DisplayStats
    (
        uint64_t        StartTime,                      // [in]
        uint64_t        EndTime,                        // [in]
        uint64_t        BytesWritten,                   // [in]
        uint64_t        OriginalStartTime,              // [in]
        uint64_t        BytesWrittenAllTime             // [in]
    )
{
    double      currentRate;
    double      totalRate;

    currentRate = 1000.0 * (double)(BytesWritten) / (double)(EndTime - StartTime);
    totalRate = 1000.0 * (double)(BytesWrittenAllTime) / (double)(EndTime - OriginalStartTime);

    printf( "Block: "); DisplayDataAmount( BytesWritten );
    printf( "  Rate: "); DisplayFillRate( currentRate );

    printf( "  |  " );
    printf( "Total: "); DisplayDataAmount( BytesWrittenAllTime );
    printf( "  AvgRate: "); DisplayFillRate( totalRate );

    printf( "\n" );
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  WriteInSmallBlocks
//
//  Writes the specified amount of data to the file in small chunks at a time.
//  Returns number of bytes written
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
static
uint32_t
    WriteInSmallBlocks
    (
        FILE*           File,           // [in,out]
        uint8_t const*  Buffer,         // [in]
        uint32_t        BufferSize      // [in]
    )
{
    uint32_t    amountLeft = BufferSize;
    uint32_t    chunkSize;
    size_t      amount;
    uint32_t    totalWritten = 0;
    uint32_t    offset = 0;

    while( amountLeft > 0 )
    {
        chunkSize = __min( amountLeft, 512 );
        amount = fwrite( Buffer+offset, 1, chunkSize, File );
        if( amount <= 0 )
        {
            break;
        }

        totalWritten += (uint32_t) amount;
        offset += (uint32_t) amount;
        amountLeft -= (uint32_t) amount;
    }

    return totalWritten;
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//  main
//
//  Program entry point
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
int
    main
    (
        int             ArgC,
        char**          ArgV
    )
{
    char const*     fileName;
    Rc4Context      rc4 = {0};
    FILE*           file = NULL;
    uint8_t*        buffer = NULL;
    uint32_t        reuseLoopCounter;
    uint32_t        i;
    uint32_t        amountWritten;
    bool            keepGoing = true;
    uint64_t        originalStartTime;
    uint64_t        startTime;
    uint64_t        endTime;
    uint64_t        totalWritten;
    uint64_t        writtenSinceDisplay;

    printf( "PushFill Version " VERSION_STR " - waterjuice.org\n" );

    if( 2 != ArgC )
    {
        printf(
            "Syntax\n"
            "   PushFill <FileName>\n" );
        return 1;
    }

    fileName = ArgV[1];

    buffer = malloc( FILL_BUFFER_SIZE );
    if( NULL == buffer )
    {
        printf( "Memory fail\n" );
        exit( 1 );
    }

    SeedStreamWithRandom( &rc4 );

    totalWritten = 0;
    writtenSinceDisplay = 0;

    startTime = GetMilliSecondTime( );
    originalStartTime = startTime;

    file = fopen( fileName, "ab" );
    if( NULL == file )
    {
        printf( "Unable to create file: %s\n", fileName );
        exit( 2 );
    }

    while( keepGoing )
    {

        // Fill buffer with random
        Rc4Output( &rc4, buffer, FILL_BUFFER_SIZE );

        for( reuseLoopCounter=0; reuseLoopCounter<256; reuseLoopCounter++ )
        {
            if( reuseLoopCounter > 0 )
            {
                // To avoid the cost of generating RC4 for each 10M block we simply increment 1 to every byte in the block
                // for the next 255 iterations. The blocks will still be different, however the speed is almost the same
                // as not changing it at all.
                for( i=0; i<FILL_BUFFER_SIZE; i++ )
                {
                    buffer[i] += 1;
                }
            }

            // Write buffer
            amountWritten = (uint32_t)fwrite( buffer, 1, FILL_BUFFER_SIZE, file );
            if( 0 == amountWritten )
            {
                amountWritten = WriteInSmallBlocks( file, buffer, FILL_BUFFER_SIZE );
            }
            totalWritten += amountWritten;
            writtenSinceDisplay += amountWritten;
            if( FILL_BUFFER_SIZE != amountWritten )
            {
                keepGoing = false;
                break;
            }

            endTime = GetMilliSecondTime( );
            if( endTime - startTime > MIN_MILLISECONDS_BETWEEN_DISPLAY )
            {
                DisplayStats( startTime, endTime, writtenSinceDisplay, originalStartTime, totalWritten );
                writtenSinceDisplay = 0;
                startTime = GetMilliSecondTime( );

                fclose( file );
                file = fopen( fileName, "ab" );
                if( NULL == file )
                {
                    printf( "Error reopening file" );
                    exit( 2 );
                }
            }
        }
    }

    endTime = GetMilliSecondTime( );
    DisplayStats( startTime, endTime, writtenSinceDisplay, originalStartTime, totalWritten );

    fclose( file );
    free( buffer );

    printf( "Finished\n" );

    return 0;
}
