// ---------------------------------------------------------------------------------------
//
//	cli.go
//	------
//
//	CLI argument parsing, help text, and dispatch. Provides Python 3.14-style
//	coloured help output with TTY detection.
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
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// ---------------------------------------------------------------------------------------
//
//	Constants
//
// ---------------------------------------------------------------------------------------

const licenceText = `This is free and unencumbered software released into the public domain.

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

For more information, please refer to <https://unlicense.org>
`

// ---------------------------------------------------------------------------------------
//
//	Run
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// Run is the main entry point called from main.go.
func Run(version string) {
	args := os.Args[1:]
	opts, err := parseArgs(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	if opts.showHelp {
		printUsage()
		os.Exit(0)
	}
	if opts.showVersion {
		fmt.Printf("pushfill %s\n", version)
		os.Exit(0)
	}
	if opts.showLicense {
		printColouredLicence(version)
		os.Exit(0)
	}

	os.Exit(runFill(version, opts))
}

// ---------------------------------------------------------------------------------------
//
//	Options
//
// ---------------------------------------------------------------------------------------

type options struct {
	path        string
	size        string
	keep        bool
	workers     int
	chunkSize   int
	fat32       bool
	maxFileSize string
	noColour    bool
	verbose     bool
	showHelp    bool
	showVersion bool
	showLicense bool
}

// ---------------------------------------------------------------------------------------
//
//	Argument Parsing
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// parseArgs manually parses CLI arguments to replicate the Python argparse behaviour.
func parseArgs(args []string) (options, error) {
	opts := options{
		path:      ".",
		workers:   0, // 0 = auto-detect
		chunkSize: 4,
	}

	positionalUsed := false
	i := 0
	for i < len(args) {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			opts.showHelp = true
			return opts, nil
		case "--version":
			opts.showVersion = true
			return opts, nil
		case "--license", "--licence":
			opts.showLicense = true
			return opts, nil
		case "-s", "--size":
			i++
			if i >= len(args) {
				return opts, fmt.Errorf("argument -s/--size: expected one argument")
			}
			opts.size = args[i]
		case "-k", "--keep":
			opts.keep = true
		case "-w", "--workers":
			i++
			if i >= len(args) {
				return opts, fmt.Errorf("argument -w/--workers: expected one argument")
			}
			n, err := strconv.Atoi(args[i])
			if err != nil {
				return opts, fmt.Errorf("argument -w/--workers: invalid int value: '%s'", args[i])
			}
			opts.workers = n
		case "-c", "--chunk-size":
			i++
			if i >= len(args) {
				return opts, fmt.Errorf("argument -c/--chunk-size: expected one argument")
			}
			n, err := strconv.Atoi(args[i])
			if err != nil {
				return opts, fmt.Errorf("argument -c/--chunk-size: invalid int value: '%s'", args[i])
			}
			opts.chunkSize = n
		case "-f", "--fat32":
			opts.fat32 = true
		case "-m", "--max-file-size":
			i++
			if i >= len(args) {
				return opts, fmt.Errorf("argument -m/--max-file-size: expected one argument")
			}
			opts.maxFileSize = args[i]
		case "-n", "--no-colour", "--no-color":
			opts.noColour = true
		case "-v", "--verbose":
			opts.verbose = true
		default:
			if strings.HasPrefix(arg, "-") {
				return opts, fmt.Errorf("unrecognised arguments: %s", arg)
			}
			if positionalUsed {
				return opts, fmt.Errorf("unrecognised arguments: %s", arg)
			}
			opts.path = arg
			positionalUsed = true
		}
		i++
	}

	return opts, nil
}

// ---------------------------------------------------------------------------------------
//
//	Size Parsing
//
// ---------------------------------------------------------------------------------------

var sizeRe = regexp.MustCompile(`(?i)^(\d+(?:\.\d+)?)\s*([A-Za-z]*)\s*$`)

var sizeUnits = map[string]int64{
	"B":  1,
	"K":  1024,
	"KB": 1024,
	"M":  1024 * 1024,
	"MB": 1024 * 1024,
	"G":  1024 * 1024 * 1024,
	"GB": 1024 * 1024 * 1024,
	"T":  1024 * 1024 * 1024 * 1024,
	"TB": 1024 * 1024 * 1024 * 1024,
}

// ---------------------------------------------------------------------------------------
// parseSize parses a human-readable size string into bytes.
// Accepts formats like: 100M, 10G, 1T, 500MB, 1024, 4096B
func parseSize(s string) (int64, error) {
	s = strings.TrimSpace(s)
	m := sizeRe.FindStringSubmatch(s)
	if m == nil {
		return 0, fmt.Errorf("invalid size: %q", s)
	}
	value, err := strconv.ParseFloat(m[1], 64)
	if err != nil {
		return 0, fmt.Errorf("invalid size: %q", s)
	}
	unit := strings.ToUpper(m[2])
	if unit == "" {
		unit = "B"
	}
	mult, ok := sizeUnits[unit]
	if !ok {
		return 0, fmt.Errorf("unknown size unit: %q", m[2])
	}
	return int64(value * float64(mult)), nil
}

// ---------------------------------------------------------------------------------------
//
//	Help Text (Python 3.14 argparse-style coloured output)
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// printUsage prints the help text with Python 3.14 argparse-style colours.
func printUsage() {
	tty := isStdoutTerminal()
	if tty {
		h := "\033[1;34m" // heading: bold blue
		p := "\033[1;35m" // program: bold magenta
		s := "\033[32m"   // short flag: green
		l := "\033[36m"   // long flag: cyan
		m := "\033[33m"   // metavar: yellow
		S := "\033[1;32m" // short flag bold: bold green
		L := "\033[1;36m" // long flag bold: bold cyan
		M := "\033[1;33m" // metavar bold: bold yellow
		r := "\033[0m"    // reset

		fmt.Printf("%susage: %s%spushfill%s [%s-h%s] [%s--version%s] [%s-s%s %sSIZE%s] [%s-k%s] [%s-w%s %sWORKERS%s] [%s-c%s %sCHUNK_SIZE%s]\n",
			h, r, p, r, s, r, l, r, s, r, m, r, s, r, s, r, m, r, s, r, m, r)
		fmt.Printf("                [%s-f%s] [%s-m%s %sMAX_FILE_SIZE%s] [%s-n%s] [%s-v%s]\n",
			s, r, s, r, m, r, s, r, s, r)
		fmt.Printf("                [%spath%s]\n", m, r)
		fmt.Println()
		fmt.Println("Fill a disk with pseudo-random data as fast as possible, then clean up.")
		fmt.Println()
		fmt.Println("Designed to push out old data from SSDs by writing pseudo-random bytes")
		fmt.Println("until the target size is reached or the disk is full.")
		fmt.Println()
		fmt.Println("Examples:")
		fmt.Println("  pushfill                         # Fill current directory until disk is full")
		fmt.Println("  pushfill /tmp                    # Fill /tmp until disk is full, then delete")
		fmt.Println("  pushfill /tmp/fill.bin           # Write to a single file")
		fmt.Println("  pushfill /tmp --size 10G         # Write 10 GB then delete")
		fmt.Println("  pushfill /tmp --size 500M --keep # Write 500 MB and keep files")
		fmt.Println("  pushfill /mnt/usb --fat32        # Fill a FAT32 drive (4 GiB file limit)")
		fmt.Println()
		fmt.Printf("%spositional arguments:%s\n", h, r)
		fmt.Printf("  %spath%s                  Directory or file path to fill (default: current\n", M, r)
		fmt.Println("                        directory)")
		fmt.Println()
		fmt.Printf("%soptions:%s\n", h, r)
		fmt.Printf("  %s-h%s, %s--help%s            show this help message and exit\n", S, r, L, r)
		fmt.Printf("  %s--version%s             show program's version number and exit\n", L, r)
		fmt.Printf("  %s-s%s, %s--size%s %sSIZE%s       Target size to write (e.g. 10G, 500M, 1T). Default:\n", S, r, L, r, M, r)
		fmt.Println("                        fill disk")
		fmt.Printf("  %s-k%s, %s--keep%s            Keep generated files instead of deleting them\n", S, r, L, r)
		fmt.Printf("  %s-w%s, %s--workers%s %sWORKERS%s\n", S, r, L, r, M, r)
		fmt.Println("                        Number of workers (default: CPU count)")
		fmt.Printf("  %s-c%s, %s--chunk-size%s %sCHUNK_SIZE%s\n", S, r, L, r, M, r)
		fmt.Println("                        Chunk size in MiB per write (default: 4)")
		fmt.Printf("  %s-f%s, %s--fat32%s           Limit each file to 4 GiB (for FAT32 filesystems)\n", S, r, L, r)
		fmt.Printf("  %s-m%s, %s--max-file-size%s %sMAX_FILE_SIZE%s\n", S, r, L, r, M, r)
		fmt.Println("                        Maximum size per file (e.g. 2G). Overrides --fat32")
		fmt.Printf("  %s-n%s, %s--no-colour%s, %s--no-color%s\n", S, r, L, r, L, r)
		fmt.Println("                        Disable coloured output")
		fmt.Printf("  %s-v%s, %s--verbose%s        Show verbose output\n", S, r, L, r)
	} else {
		fmt.Println("usage: pushfill [-h] [--version] [-s SIZE] [-k] [-w WORKERS] [-c CHUNK_SIZE]")
		fmt.Println("                [-f] [-m MAX_FILE_SIZE] [-n] [-v]")
		fmt.Println("                [path]")
		fmt.Println()
		fmt.Println("Fill a disk with pseudo-random data as fast as possible, then clean up.")
		fmt.Println()
		fmt.Println("Designed to push out old data from SSDs by writing pseudo-random bytes")
		fmt.Println("until the target size is reached or the disk is full.")
		fmt.Println()
		fmt.Println("Examples:")
		fmt.Println("  pushfill                         # Fill current directory until disk is full")
		fmt.Println("  pushfill /tmp                    # Fill /tmp until disk is full, then delete")
		fmt.Println("  pushfill /tmp/fill.bin           # Write to a single file")
		fmt.Println("  pushfill /tmp --size 10G         # Write 10 GB then delete")
		fmt.Println("  pushfill /tmp --size 500M --keep # Write 500 MB and keep files")
		fmt.Println("  pushfill /mnt/usb --fat32        # Fill a FAT32 drive (4 GiB file limit)")
		fmt.Println()
		fmt.Println("positional arguments:")
		fmt.Println("  path                  Directory or file path to fill (default: current")
		fmt.Println("                        directory)")
		fmt.Println()
		fmt.Println("options:")
		fmt.Println("  -h, --help            show this help message and exit")
		fmt.Println("  --version             show program's version number and exit")
		fmt.Println("  -s, --size SIZE       Target size to write (e.g. 10G, 500M, 1T). Default:")
		fmt.Println("                        fill disk")
		fmt.Println("  -k, --keep            Keep generated files instead of deleting them")
		fmt.Println("  -w, --workers WORKERS")
		fmt.Println("                        Number of workers (default: CPU count)")
		fmt.Println("  -c, --chunk-size CHUNK_SIZE")
		fmt.Println("                        Chunk size in MiB per write (default: 4)")
		fmt.Println("  -f, --fat32           Limit each file to 4 GiB (for FAT32 filesystems)")
		fmt.Println("  -m, --max-file-size MAX_FILE_SIZE")
		fmt.Println("                        Maximum size per file (e.g. 2G). Overrides --fat32")
		fmt.Println("  -n, --no-colour, --no-color")
		fmt.Println("                        Disable coloured output")
		fmt.Println("  -v, --verbose         Show verbose output")
	}
}

// ---------------------------------------------------------------------------------------
// printColouredLicence prints the colourised licence text (matching the Python version).
func printColouredLicence(version string) {
	tty := isStdoutTerminal()
	if !tty {
		fmt.Print(licenceText)
		return
	}

	fmt.Println()
	fmt.Printf("  %s\n", colorBold(colorCyan("pushfill "+version, true), true))
	fmt.Printf("  %s\n", colorDim(strings.Repeat("─", 40), true))
	fmt.Println()
	fmt.Printf("  %s\n", colorBold(colorGreen("This is free and unencumbered software", true), true))
	fmt.Printf("  %s\n", colorGreen("released into the public domain.", true))
	fmt.Println()
	fmt.Printf("  %s %s%s %s%s %s%s %s%s %s%s %s\n",
		colorCyan("Anyone is free to", true),
		colorBold(colorCyan("copy", true), true), colorCyan(",", true),
		colorBold(colorCyan("modify", true), true), colorCyan(",", true),
		colorBold(colorCyan("publish", true), true), colorCyan(",", true),
		colorBold(colorCyan("use", true), true), colorCyan(",", true),
		colorBold(colorCyan("compile", true), true), colorCyan(",", true),
		colorBold(colorCyan("sell", true), true)+colorCyan(", or", true))
	fmt.Printf("  %s\n", colorCyan("distribute this software, either in source code form", true))
	fmt.Printf("  %s %s%s\n",
		colorCyan("or as a compiled binary, for", true),
		colorBold(colorCyan("any purpose", true), true),
		colorCyan(", commercial", true))
	fmt.Printf("  %s\n", colorCyan("or non-commercial, and by any means.", true))
	fmt.Println()
	fmt.Printf("  %s\n", colorMagenta("In jurisdictions that recognize copyright laws,", true))
	fmt.Printf("  %s\n", colorMagenta("the author or authors of this software dedicate", true))
	fmt.Printf("  %s\n", colorMagenta("any and all copyright interest in the software to", true))
	fmt.Printf("  %s\n", colorMagenta("the public domain.", true))
	fmt.Println()
	warranty := []string{
		`THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY`,
		"OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT",
		"LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS",
		"FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.",
	}
	for _, line := range warranty {
		fmt.Printf("  %s\n", colorDim(line, true))
	}
	fmt.Println()
	fmt.Printf("  %s %s\n",
		colorYellow("For more information:", true),
		colorBold(colorCyan("https://unlicense.org", true), true))
	fmt.Println()
}

// ---------------------------------------------------------------------------------------
//
//	Terminal / Colour Helpers
//
// ---------------------------------------------------------------------------------------

// colourEnabled tracks whether colour output is enabled. Set to false by --no-colour.
var colourEnabled = true

// ---------------------------------------------------------------------------------------
// isStdoutTerminal reports whether stdout is connected to a terminal (TTY).
func isStdoutTerminal() bool {
	if !colourEnabled {
		return false
	}
	info, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return info.Mode()&os.ModeCharDevice != 0
}

// ---------------------------------------------------------------------------------------
// colorBold wraps s in ANSI bold codes if tty is true.
func colorBold(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[1m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// colorDim wraps s in ANSI dim codes if tty is true.
func colorDim(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[2m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// colorGreen wraps s in ANSI green codes if tty is true.
func colorGreen(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[32m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// colorYellow wraps s in ANSI yellow codes if tty is true.
func colorYellow(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[33m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// colorCyan wraps s in ANSI cyan codes if tty is true.
func colorCyan(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[36m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// colorMagenta wraps s in ANSI magenta codes if tty is true.
func colorMagenta(s string, tty bool) string {
	if !tty {
		return s
	}
	return "\033[35m" + s + "\033[0m"
}

// ---------------------------------------------------------------------------------------
// stripAnsi removes ANSI escape codes from a string.
func stripAnsi(s string) string {
	return ansiRe.ReplaceAllString(s, "")
}

var ansiRe = regexp.MustCompile(`\033\[[0-9;]*m`)

// ---------------------------------------------------------------------------------------
// visibleLen returns the visible length of a string (excluding ANSI codes).
// Uses RuneCountInString so multi-byte UTF-8 characters (like █ and ░) are
// counted as 1 column each, matching terminal rendering.
func visibleLen(s string) int {
	return utf8.RuneCountInString(stripAnsi(s))
}
