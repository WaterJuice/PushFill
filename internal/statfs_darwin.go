// ---------------------------------------------------------------------------------------
//
//	statfs_darwin.go
//	----------------
//
//	macOS-specific filesystem type name extraction from Statfs_t.Fstypename.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
// ---------------------------------------------------------------------------------------
package internal

import (
	"strings"
	"syscall"
)

// ---------------------------------------------------------------------------------------
// statfsTypeName extracts the filesystem type name from a Statfs_t on macOS.
func statfsTypeName(stat *syscall.Statfs_t) string {
	var b []byte
	for _, c := range stat.Fstypename {
		if c == 0 {
			break
		}
		b = append(b, byte(c))
	}
	return strings.ToLower(string(b))
}
