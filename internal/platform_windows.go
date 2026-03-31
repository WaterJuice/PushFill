// ---------------------------------------------------------------------------------------
//
//	platform_windows.go
//	-------------------
//
//	Windows-specific implementations for disk usage queries, terminal width
//	detection, and filesystem type detection.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
// ---------------------------------------------------------------------------------------
//go:build windows

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
//	Windows API handles (resolved once at package init)
//
// ---------------------------------------------------------------------------------------

var (
	kernel32                   = syscall.NewLazyDLL("kernel32.dll")
	procGetDiskFreeSpaceEx     = kernel32.NewProc("GetDiskFreeSpaceExW")
	procGetVolumeInformation   = kernel32.NewProc("GetVolumeInformationW")
	procGetConsoleScreenBuffer = kernel32.NewProc("GetConsoleScreenBufferInfo")
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
	var freeBytesAvailable, totalBytes, totalFreeBytes uint64
	pathPtr, _ := syscall.UTF16PtrFromString(path)
	ret, _, _ := procGetDiskFreeSpaceEx.Call(
		uintptr(unsafe.Pointer(pathPtr)),
		uintptr(unsafe.Pointer(&freeBytesAvailable)),
		uintptr(unsafe.Pointer(&totalBytes)),
		uintptr(unsafe.Pointer(&totalFreeBytes)),
	)
	if ret == 0 {
		return diskUsage{}
	}
	return diskUsage{
		total: totalBytes,
		free:  freeBytesAvailable,
		used:  totalBytes - freeBytesAvailable,
	}
}

// ---------------------------------------------------------------------------------------
//
//	Filesystem Detection
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// detectFilesystemLimit auto-detects filesystem file size limits on Windows.
// Uses GetVolumeInformationW to check for FAT-family filesystems.
func detectFilesystemLimit(targetDir string) int64 {
	// Get the volume root (e.g. "C:\\")
	root := targetDir
	if len(root) >= 2 && root[1] == ':' {
		root = root[:3]
	} else {
		return 0
	}
	rootPtr, _ := syscall.UTF16PtrFromString(root)
	fsNameBuf := make([]uint16, 256)

	ret, _, _ := procGetVolumeInformation.Call(
		uintptr(unsafe.Pointer(rootPtr)),
		0, 0, 0, 0, 0,
		uintptr(unsafe.Pointer(&fsNameBuf[0])),
		256,
	)
	if ret == 0 {
		return 0
	}

	fsName := syscall.UTF16ToString(fsNameBuf)
	switch fsName {
	case "FAT", "FAT16", "FAT32", "MSDOS", "VFAT":
		return fat32MaxFileSize
	}
	return 0
}

// ---------------------------------------------------------------------------------------
//
//	Terminal Width
//
// ---------------------------------------------------------------------------------------

type consoleScreenBufferInfo struct {
	Size              [2]int16
	CursorPosition    [2]int16
	Attributes        uint16
	Window            [4]int16
	MaximumWindowSize [2]int16
}

// ---------------------------------------------------------------------------------------
// getTerminalWidth returns the terminal width, defaulting to 80 if unavailable.
func getTerminalWidth() int {
	handle := syscall.Handle(os.Stdout.Fd())
	var info consoleScreenBufferInfo
	ret, _, _ := procGetConsoleScreenBuffer.Call(
		uintptr(handle),
		uintptr(unsafe.Pointer(&info)),
	)
	if ret == 0 {
		return 80
	}
	width := int(info.Window[3]-info.Window[1]) + 1
	if width <= 0 {
		return 80
	}
	return width
}
