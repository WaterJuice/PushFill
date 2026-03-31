// ---------------------------------------------------------------------------------------
//
//	statfs_linux.go
//	---------------
//
//	Linux-specific filesystem type detection. On Linux, Statfs_t does not have
//	Fstypename, so we read /proc/mounts to identify FAT-family filesystems.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
// ---------------------------------------------------------------------------------------
package internal

import (
	"bufio"
	"os"
	"strings"
	"syscall"
)

// ---------------------------------------------------------------------------------------
// statfsTypeName reads /proc/mounts to find the filesystem type for the path
// that was passed to Statfs. On Linux, Statfs_t does not contain a type name
// string, so we resolve it via mount table lookup instead.
//
// The path parameter is embedded in the caller's Statfs call; since we cannot
// recover it from the struct, detectFilesystemLimit in platform_unix.go is
// overridden below for Linux.
func statfsTypeName(_ *syscall.Statfs_t) string {
	return ""
}

// ---------------------------------------------------------------------------------------
// detectFilesystemLimitLinux reads /proc/mounts to detect FAT-family filesystems.
// This overrides the generic Unix version via init().
func detectFilesystemLimitLinux(targetDir string) int64 {
	f, err := os.Open("/proc/mounts")
	if err != nil {
		return 0
	}
	defer f.Close()

	bestMount := ""
	bestFSType := ""
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		parts := strings.Fields(scanner.Text())
		if len(parts) < 3 {
			continue
		}
		mountPoint := strings.ReplaceAll(parts[1], "\\040", " ")
		fstype := strings.ToLower(parts[2])
		var matches bool
		if mountPoint == "/" {
			matches = true
		} else {
			matches = targetDir == mountPoint || strings.HasPrefix(targetDir, mountPoint+"/")
		}
		if matches && len(mountPoint) > len(bestMount) {
			bestMount = mountPoint
			bestFSType = fstype
		}
	}

	if fatFSTypes[bestFSType] {
		return fat32MaxFileSize
	}
	return 0
}

// ---------------------------------------------------------------------------------------
// init replaces the generic Unix detectFilesystemLimit with the Linux
// /proc/mounts-based version.
func init() {
	detectFilesystemLimitFunc = detectFilesystemLimitLinux
}
