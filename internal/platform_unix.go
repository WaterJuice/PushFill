// ---------------------------------------------------------------------------------------
//
//	platform_unix.go
//	----------------
//
//	Unix-specific (macOS + Linux) implementations for disk usage queries,
//	terminal width detection, and filesystem type detection.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
// ---------------------------------------------------------------------------------------
//go:build !windows

package internal

// ---------------------------------------------------------------------------------------
//
//	Imports
//
// ---------------------------------------------------------------------------------------

import (
	"os"
	"syscall"
	"unsafe"
)

// ---------------------------------------------------------------------------------------
//
//	Disk Usage
//
// ---------------------------------------------------------------------------------------

type diskUsage struct {
	total uint64
	free  uint64
	used  uint64
}

// ---------------------------------------------------------------------------------------
// getDiskUsage returns disk usage statistics for the given path.
func getDiskUsage(path string) diskUsage {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return diskUsage{}
	}
	total := stat.Blocks * uint64(stat.Bsize)
	free := stat.Bavail * uint64(stat.Bsize)
	used := total - free
	return diskUsage{total: total, free: free, used: used}
}

// ---------------------------------------------------------------------------------------
//
//	Filesystem Detection
//
// ---------------------------------------------------------------------------------------

// Known FAT-family filesystem type names (lowercase) for auto-detection
var fatFSTypes = map[string]bool{
	"msdos": true, "vfat": true, "fat32": true, "fat16": true, "fat": true,
}

// detectFilesystemLimitFunc is the active filesystem limit detector.
// On macOS this uses statfs Fstypename; on Linux it is replaced via init()
// in statfs_linux.go to read /proc/mounts instead.
var detectFilesystemLimitFunc = detectFilesystemLimitUnix

// ---------------------------------------------------------------------------------------
// detectFilesystemLimit auto-detects filesystem file size limits.
// Returns fat32MaxFileSize if a FAT-family filesystem is detected, otherwise 0.
func detectFilesystemLimit(targetDir string) int64 {
	return detectFilesystemLimitFunc(targetDir)
}

// ---------------------------------------------------------------------------------------
// detectFilesystemLimitUnix is the default Unix implementation using statfs.
// Works on macOS where Statfs_t has Fstypename; on Linux statfsTypeName
// returns "" so this won't detect FAT (Linux overrides via init).
func detectFilesystemLimitUnix(targetDir string) int64 {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(targetDir, &stat); err != nil {
		return 0
	}
	fstype := statfsTypeName(&stat)
	if fatFSTypes[fstype] {
		return fat32MaxFileSize
	}
	return 0
}

// ---------------------------------------------------------------------------------------
//
//	Terminal Width
//
// ---------------------------------------------------------------------------------------

type winsize struct {
	Row    uint16
	Col    uint16
	Xpixel uint16
	Ypixel uint16
}

// ---------------------------------------------------------------------------------------
// getTerminalWidth returns the terminal width, defaulting to 80 if unavailable.
func getTerminalWidth() int {
	var ws winsize
	fd := os.Stdout.Fd()
	_, _, errno := syscall.Syscall(
		syscall.SYS_IOCTL,
		fd,
		uintptr(syscall.TIOCGWINSZ),
		uintptr(unsafe.Pointer(&ws)),
	)
	if errno != 0 || ws.Col == 0 {
		return 80
	}
	return int(ws.Col)
}
