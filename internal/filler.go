// ---------------------------------------------------------------------------------------
//
//	filler.go
//	---------
//
//	Core disk fill logic. Spawns goroutine-based workers that generate random
//	data using crypto/rand and write to disk files. Uses shared atomic counters
//	for progress tracking.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
//	Authors
//	-------
//	bena (via Claude)
//
//	Version History
//	---------------
//	Feb 2026 - Created (Python)
//	Mar 2026 - Rewritten in Go
//
// ---------------------------------------------------------------------------------------
package internal

// ---------------------------------------------------------------------------------------
//
//	Imports
//
// ---------------------------------------------------------------------------------------

import (
	"crypto/rand"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// ---------------------------------------------------------------------------------------
//
//	Constants
//
// ---------------------------------------------------------------------------------------

const (
	defaultChunkSize = 4 * 1024 * 1024 // 4 MiB
	updateInterval   = 500 * time.Millisecond
	fat32MaxFileSize = (1 << 32) - 1 // 4 GiB - 1 byte
	minScrubSize     = 512           // smallest write attempt during scrub phase
)

// ---------------------------------------------------------------------------------------
//
//	Run Fill
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// runFill is the main fill operation, called from Run after argument parsing.
func runFill(version string, opts options) int {
	if opts.noColour {
		colourEnabled = false
	}

	// Resolve target path — detect file vs directory
	rawPath, err := filepath.Abs(opts.path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return 1
	}

	var targetDir string
	var outputPath string // empty = directory mode

	info, err := os.Stat(rawPath)
	if err == nil {
		if info.IsDir() {
			targetDir = rawPath
		} else {
			// Existing file — single-file mode
			targetDir = filepath.Dir(rawPath)
			outputPath = rawPath
		}
	} else if os.IsNotExist(err) {
		parent := filepath.Dir(rawPath)
		pinfo, perr := os.Stat(parent)
		if perr != nil || !pinfo.IsDir() {
			fmt.Fprintf(os.Stderr, "Error: %s is not a directory\n", parent)
			return 1
		}
		targetDir = parent
		outputPath = rawPath
	} else {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return 1
	}

	// Parse target size
	var targetSize int64
	if opts.size != "" {
		targetSize, err = parseSize(opts.size)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			return 1
		}
	}

	// Determine max file size
	var maxFileSize int64
	if opts.maxFileSize != "" {
		maxFileSize, err = parseSize(opts.maxFileSize)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			return 1
		}
	} else if opts.fat32 {
		maxFileSize = fat32MaxFileSize
	} else {
		detected := detectFilesystemLimit(targetDir)
		if detected > 0 {
			maxFileSize = detected
			fmt.Println("  Detected FAT32 filesystem — files limited to 4 GiB each")
		}
	}

	// Single-file mode on FAT32 won't work
	if outputPath != "" && maxFileSize > 0 {
		fmt.Fprintln(os.Stderr,
			"Error: single-file mode is not compatible with FAT32 filesystems.\n"+
				"       FAT32 has a 4 GiB per-file limit, so filling a disk requires\n"+
				"       multiple files. Specify a directory path instead.")
		return 1
	}

	// Determine number of workers
	numWorkers := opts.workers
	if outputPath != "" {
		numWorkers = 1
	} else if numWorkers <= 0 {
		numWorkers = runtime.NumCPU()
		if numWorkers < 1 {
			numWorkers = 4
		}
	}
	if numWorkers < 1 {
		fmt.Fprintln(os.Stderr, "Error: --workers must be at least 1")
		return 1
	}

	// Chunk size (argument is in MiB)
	chunkSize := opts.chunkSize * 1024 * 1024

	// Snapshot initial disk free space
	du := getDiskUsage(targetDir)
	initialFree := du.free

	// Create shared state
	counters := make([]atomic.Int64, numWorkers)
	var stopFlag atomic.Bool

	// Install signal handler
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	var interrupted atomic.Bool

	go func() {
		<-sigChan
		interrupted.Store(true)
		stopFlag.Store(true)
	}()

	// Calculate per-worker byte budget
	var perWorker, remainder int64
	if targetSize > 0 {
		perWorker = targetSize / int64(numWorkers)
		remainder = targetSize % int64(numWorkers)
	}

	// Scan for existing pushfill files to avoid overwriting
	fileSeqStarts := make([]int, numWorkers)
	if outputPath == "" {
		entries, _ := filepath.Glob(filepath.Join(targetDir, "pushfill_*_*.bin"))
		for _, entry := range entries {
			base := filepath.Base(entry)
			base = base[:len(base)-4] // strip .bin
			parts := strings.Split(base, "_")
			if len(parts) == 3 {
				wid, wErr := strconv.Atoi(parts[1])
				seq, sErr := strconv.Atoi(parts[2])
				if wErr != nil || sErr != nil {
					continue
				}
				if wid < numWorkers && seq+1 > fileSeqStarts[wid] {
					fileSeqStarts[wid] = seq + 1
				}
			}
		}
	}

	// Spawn workers
	var wg sync.WaitGroup
	for i := 0; i < numWorkers; i++ {
		workerMax := perWorker
		if i == numWorkers-1 {
			workerMax += remainder
		}
		workerOutput := ""
		if outputPath != "" && i == 0 {
			workerOutput = outputPath
		}
		wg.Add(1)
		go func(id int, maxBytes int64, outPath string, seqStart int) {
			defer wg.Done()
			worker(id, targetDir, chunkSize, &counters[id], &stopFlag, maxFileSize, maxBytes, outPath, seqStart)
		}(i, workerMax, workerOutput, fileSeqStarts[i])
	}

	// Determine goal for progress display
	var goal int64
	if targetSize > 0 {
		goal = targetSize
	} else if initialFree > 0 {
		goal = int64(initialFree)
	}

	// Monitor loop
	display := NewDisplay(targetDir, targetSize, goal, numWorkers, version)

	// Channel to detect all workers done
	doneChan := make(chan struct{})
	go func() {
		wg.Wait()
		close(doneChan)
	}()

	ticker := time.NewTicker(updateInterval)
	defer ticker.Stop()

monitorLoop:
	for {
		select {
		case <-ticker.C:
			var total int64
			for i := 0; i < numWorkers; i++ {
				total += counters[i].Load()
			}

			// Refresh goal when filling to disk capacity
			if targetSize == 0 {
				du := getDiskUsage(targetDir)
				if du.free > 0 {
					goal = total + int64(du.free)
					display.SetGoal(goal)
				}
			}

			display.Update(total)

			// Check if target size reached
			if targetSize > 0 && total >= targetSize {
				stopFlag.Store(true)
				break monitorLoop
			}

		case <-doneChan:
			break monitorLoop
		}
	}

	// Signal stop and wait
	stopFlag.Store(true)
	wg.Wait()

	// Restore signal handling
	signal.Stop(sigChan)

	var total int64
	for i := 0; i < numWorkers; i++ {
		total += counters[i].Load()
	}
	display.FinalReport(total, interrupted.Load())

	// Cleanup
	if !opts.keep {
		cleanup(targetDir, outputPath)
	} else {
		if outputPath != "" {
			fmt.Printf("  File kept at %s\n", outputPath)
		} else {
			fmt.Printf("  Files kept in %s\n", targetDir)
		}
	}

	return 0
}

// ---------------------------------------------------------------------------------------
//
//	Worker
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// worker writes pseudo-random data to file(s) until stopped or disk full.
func worker(
	workerID int,
	targetDir string,
	chunkSize int,
	counter *atomic.Int64,
	stop *atomic.Bool,
	maxFileSize int64,
	maxBytes int64,
	outputPath string,
	fileSeqStart int,
) {
	buf := make([]byte, chunkSize)
	var localWritten int64
	fileSeq := fileSeqStart
	var fileBytes int64

	openFile := func() (*os.File, error) {
		fileBytes = 0
		if outputPath != "" {
			return os.OpenFile(outputPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
		}
		path := filepath.Join(targetDir, fmt.Sprintf("pushfill_%04d_%04d.bin", workerID, fileSeq))
		fileSeq++
		return os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
	}

	writeChunk := func(f **os.File, data []byte) (bool, error) {
		remaining := data
		for len(remaining) > 0 {
			// Check file size limit — rotate if needed
			if maxFileSize > 0 && fileBytes >= maxFileSize {
				(*f).Close()
				var err error
				*f, err = openFile()
				if err != nil {
					return false, err
				}
			}

			writeSize := len(remaining)
			if maxFileSize > 0 {
				limit := int(maxFileSize - fileBytes)
				if writeSize > limit {
					writeSize = limit
				}
			}

			n, err := (*f).Write(remaining[:writeSize])
			fileBytes += int64(n)
			localWritten += int64(n)
			counter.Store(localWritten)
			remaining = remaining[n:]

			if err != nil {
				if isENOSPC(err) {
					return false, nil // disk full
				}
				if isEFBIG(err) {
					if outputPath != "" {
						return false, nil
					}
					(*f).Close()
					var ferr error
					*f, ferr = openFile()
					if ferr != nil {
						return false, ferr
					}
					continue
				}
				return false, err
			}
		}
		return true, nil
	}

	f, err := openFile()
	if err != nil {
		return
	}
	defer f.Close()

	consecutiveScrubFailures := 0
	maxScrubRetries := 3

	for !stop.Load() {
		// Main phase: generate random data and write
		diskFull := false

		for !stop.Load() && !diskFull {
			if maxBytes > 0 && localWritten >= maxBytes {
				return
			}

			// Generate random data
			_, err := rand.Read(buf)
			if err != nil {
				return
			}

			data := buf
			if maxBytes > 0 {
				remaining := maxBytes - localWritten
				if remaining < int64(chunkSize) {
					data = buf[:remaining]
				}
			}

			ok, werr := writeChunk(&f, data)
			if werr != nil {
				return
			}
			if !ok {
				diskFull = true
			}
		}

		if stop.Load() || (maxBytes > 0 && localWritten >= maxBytes) {
			return
		}

		if !diskFull {
			return
		}

		// Scrub phase: fill remaining space with progressively smaller writes
		scrubSize := chunkSize / 2
		wroteInScrub := false
		for scrubSize >= minScrubSize && !stop.Load() {
			_, err := rand.Read(buf[:scrubSize])
			if err != nil {
				return
			}
			ok, werr := writeChunk(&f, buf[:scrubSize])
			if werr != nil {
				return
			}
			if !ok {
				scrubSize /= 2
				continue
			}
			wroteInScrub = true
		}

		if !wroteInScrub {
			consecutiveScrubFailures++
			if consecutiveScrubFailures >= maxScrubRetries {
				return
			}
			time.Sleep(500 * time.Millisecond)
		} else {
			consecutiveScrubFailures = 0
		}
	}
}

// ---------------------------------------------------------------------------------------
//
//	Cleanup
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// cleanup deletes generated files.
func cleanup(targetDir string, outputPath string) {
	// Ignore SIGINT during cleanup
	signal.Ignore(syscall.SIGINT)

	if outputPath != "" {
		if err := os.Remove(outputPath); err == nil {
			fmt.Println("  Cleaned up 1 file.")
		}
		return
	}
	count := 0
	entries, _ := filepath.Glob(filepath.Join(targetDir, "pushfill_*.bin"))
	for _, entry := range entries {
		if err := os.Remove(entry); err == nil {
			count++
		}
	}
	if count > 0 {
		fmt.Printf("  Cleaned up %d file(s).\n", count)
	}
}

// ---------------------------------------------------------------------------------------
//
//	Helpers
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// isENOSPC checks if an error is ENOSPC (no space left on device).
func isENOSPC(err error) bool {
	var pathErr *os.PathError
	if errors.As(err, &pathErr) {
		return errors.Is(pathErr.Err, syscall.ENOSPC)
	}
	return errors.Is(err, syscall.ENOSPC)
}

// ---------------------------------------------------------------------------------------
// isEFBIG checks if an error is EFBIG (file too large).
func isEFBIG(err error) bool {
	var pathErr *os.PathError
	if errors.As(err, &pathErr) {
		return errors.Is(pathErr.Err, syscall.EFBIG)
	}
	return errors.Is(err, syscall.EFBIG)
}
