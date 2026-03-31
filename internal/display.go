// ---------------------------------------------------------------------------------------
//
//	display.go
//	----------
//
//	Live terminal status display for pushfill. Uses Unicode box-drawing
//	characters and ANSI escape sequences for a polished, framed display
//	showing speed, progress, disk usage, and ETA.
//
//	Replicates the exact output of the Python version's Display class.
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
	"strings"
	"time"
)

// ---------------------------------------------------------------------------------------
//
//	Constants
//
// ---------------------------------------------------------------------------------------

const emaAlpha = 0.1 // smoothing factor — lower = slower, smoother rolling average

// ---------------------------------------------------------------------------------------
//
//	Display
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// Display renders live terminal output with box-drawn framing.
type Display struct {
	targetPath   string
	targetSize   int64 // 0 = fill disk
	goalBytes    int64 // 0 = unknown
	numWorkers   int
	version      string
	startTime    time.Time
	prevTotal    int64
	prevTime     time.Time
	emaRate      float64
	emaInit      bool
	linesPrinted int
}

// ---------------------------------------------------------------------------------------
// NewDisplay creates a new Display instance.
func NewDisplay(targetPath string, targetSize int64, goalBytes int64, numWorkers int, version string) *Display {
	now := time.Now()
	return &Display{
		targetPath: targetPath,
		targetSize: targetSize,
		goalBytes:  goalBytes,
		numWorkers: numWorkers,
		version:    version,
		startTime:  now,
		prevTime:   now,
	}
}

// ---------------------------------------------------------------------------------------
// SetGoal updates the goal bytes (e.g. when purgeable space is reclaimed).
func (d *Display) SetGoal(goalBytes int64) {
	d.goalBytes = goalBytes
}

// ---------------------------------------------------------------------------------------
// Update refreshes the display with current progress.
func (d *Display) Update(totalBytes int64) {
	tty := isStdoutTerminal()
	now := time.Now()
	elapsed := now.Sub(d.startTime).Seconds()
	dt := now.Sub(d.prevTime).Seconds()

	// Calculate rates
	var instantRate float64
	if dt > 0 {
		instantRate = float64(totalBytes-d.prevTotal) / dt
	}

	// EMA smoothing
	if !d.emaInit {
		d.emaRate = instantRate
		d.emaInit = true
	} else {
		d.emaRate = emaAlpha*instantRate + (1-emaAlpha)*d.emaRate
	}

	var avgRate float64
	if elapsed > 0 {
		avgRate = float64(totalBytes) / elapsed
	}

	d.prevTotal = totalBytes
	d.prevTime = now

	// Terminal width → inner box width
	termWidth := getTerminalWidth()
	innerW := termWidth - 6
	if innerW < 46 {
		innerW = 46
	}
	if innerW > 72 {
		innerW = 72
	}
	barWidth := innerW - 10
	if barWidth < 10 {
		barWidth = 10
	}

	// Move up and clear previous output
	d.moveUpAndClear()
	var lines []string

	// Line 1: top border
	lines = append(lines, d.boxTop(innerW, tty))

	// Line 2: title + elapsed
	elapsedStr := formatTime(elapsed)
	titleLeft := colorBold(colorCyan("pushfill "+d.version, tty), tty)
	titleRight := colorDim("Elapsed "+elapsedStr, tty)
	titlePad := innerW - visibleLen(titleLeft) - visibleLen(titleRight)
	if titlePad < 1 {
		titlePad = 1
	}
	border := colorDim("│", tty)
	lines = append(lines, fmt.Sprintf("%s  %s%s%s  %s", border, titleLeft, strings.Repeat(" ", titlePad), titleRight, border))

	// Line 3: separator
	lines = append(lines, d.boxSep(innerW, tty))

	// Line 4: speed (rolling average)
	ema := d.emaRate
	speedMBs := ema / 1e6
	speedGbps := ema * 8 / 1e9
	lines = append(lines, d.boxLine(
		fmt.Sprintf("%s     %s   %s",
			colorMagenta(colorBold("Speed", tty), tty),
			colorCyan(formatFloat1(speedMBs)+" MB/s", tty),
			colorDim(fmt.Sprintf("(%.2f Gbps)", speedGbps), tty)),
		innerW, tty))

	// Line 5: average
	avgMBs := avgRate / 1e6
	avgGbps := avgRate * 8 / 1e9
	lines = append(lines, d.boxLine(
		fmt.Sprintf("%s   %s   %s",
			colorMagenta(colorBold("Average", tty), tty),
			colorCyan(formatFloat1(avgMBs)+" MB/s", tty),
			colorDim(fmt.Sprintf("(%.2f Gbps)", avgGbps), tty)),
		innerW, tty))

	// Line 6: written + ETA
	var progress float64
	var left, right string
	if d.goalBytes > 0 {
		progress = float64(totalBytes) / float64(d.goalBytes)
		if progress > 1.0 {
			progress = 1.0
		}
		sizeStr := fmt.Sprintf("%s / %s", formatSize(totalBytes), formatSize(d.goalBytes))
		left = fmt.Sprintf("%s   %s", colorMagenta(colorBold("Written", tty), tty), colorCyan(sizeStr, tty))
		if avgRate > 0 && progress < 1.0 {
			eta := float64(d.goalBytes-totalBytes) / avgRate
			right = colorYellow(fmt.Sprintf("ETA %s", formatTime(eta)), tty)
		}
	} else {
		left = fmt.Sprintf("%s   %s", colorMagenta(colorBold("Written", tty), tty), colorCyan(formatSize(totalBytes), tty))
		du := getDiskUsage(d.targetPath)
		if du.total > 0 {
			diskPct := float64(du.used) / float64(du.total) * 100
			progress = diskPct / 100.0
			right = colorDim(fmt.Sprintf("Disk %.1f%%", diskPct), tty)
		}
	}
	pad := innerW - visibleLen(left) - visibleLen(right)
	if pad < 1 {
		pad = 1
	}
	lines = append(lines, fmt.Sprintf("%s  %s%s%s  %s", border, left, strings.Repeat(" ", pad), right, border))

	// Line 7: progress bar
	pctStr := fmt.Sprintf("%.1f%%", progress*100)
	progBar := d.getBar(progress, barWidth, tty)
	lines = append(lines, d.boxLine(fmt.Sprintf("%s  %s", progBar, colorGreen(pctStr, tty)), innerW, tty))

	// Line 8: bottom border
	lines = append(lines, d.boxBottom(innerW, tty))

	output := strings.Join(lines, "\n") + "\n"
	fmt.Fprint(os.Stdout, output)
	d.linesPrinted = len(lines)
}

// ---------------------------------------------------------------------------------------
// FinalReport prints the final summary.
func (d *Display) FinalReport(totalBytes int64, interrupted bool) {
	tty := isStdoutTerminal()
	elapsed := time.Since(d.startTime).Seconds()
	var avgRate float64
	if elapsed > 0 {
		avgRate = float64(totalBytes) / elapsed
	}
	avgMBs := avgRate / 1e6
	avgGbps := avgRate * 8 / 1e9

	if interrupted {
		fmt.Fprintf(os.Stdout, "\n  %s — wrote %s in %s (%s MB/s, %.2f Gbps) across %d workers\n",
			colorYellow("Interrupted", tty),
			colorCyan(formatSize(totalBytes), tty),
			colorBold(formatTime(elapsed), tty),
			formatFloat1(avgMBs), avgGbps, d.numWorkers)
		return
	}

	// Normal completion — replace live display with summary box
	d.moveUpAndClear()
	d.linesPrinted = 0

	termWidth := getTerminalWidth()
	innerW := termWidth - 6
	if innerW < 46 {
		innerW = 46
	}
	if innerW > 72 {
		innerW = 72
	}

	var lines []string
	lines = append(lines, d.boxTop(innerW, tty))
	lines = append(lines, d.boxLine(
		fmt.Sprintf("%s  %s — wrote %s in %s",
			colorBold(colorCyan("pushfill "+d.version, tty), tty),
			colorGreen("Done", tty),
			colorCyan(formatSize(totalBytes), tty),
			colorBold(formatTime(elapsed), tty)),
		innerW, tty))
	lines = append(lines, d.boxLine(
		fmt.Sprintf("%s %s %s across %d workers",
			colorMagenta("Average:", tty),
			colorCyan(formatFloat1(avgMBs)+" MB/s", tty),
			colorDim(fmt.Sprintf("(%.2f Gbps)", avgGbps), tty),
			d.numWorkers),
		innerW, tty))
	lines = append(lines, d.boxBottom(innerW, tty))

	output := strings.Join(lines, "\n") + "\n"
	fmt.Fprint(os.Stdout, output)
}

// ---------------------------------------------------------------------------------------
//
//	Box Drawing Helpers
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
func (d *Display) moveUpAndClear() {
	if d.linesPrinted > 0 {
		fmt.Fprintf(os.Stdout, "\033[%dA\033[J", d.linesPrinted)
	}
}

// ---------------------------------------------------------------------------------------
func (d *Display) getBar(fraction float64, width int, tty bool) string {
	if fraction < 0 {
		fraction = 0
	}
	if fraction > 1 {
		fraction = 1
	}
	filled := int(fraction * float64(width))
	empty := width - filled
	barFill := colorGreen(strings.Repeat("█", filled), tty)
	barEmpty := colorDim(strings.Repeat("░", empty), tty)
	return barFill + barEmpty
}

// ---------------------------------------------------------------------------------------
func (d *Display) boxLine(content string, innerW int, tty bool) string {
	visible := visibleLen(content)
	pad := innerW - visible
	if pad < 0 {
		pad = 0
	}
	border := colorDim("│", tty)
	return fmt.Sprintf("%s  %s%s  %s", border, content, strings.Repeat(" ", pad), border)
}

// ---------------------------------------------------------------------------------------
func (d *Display) boxTop(innerW int, tty bool) string {
	return colorDim("╭"+strings.Repeat("─", innerW+4)+"╮", tty)
}

// ---------------------------------------------------------------------------------------
func (d *Display) boxSep(innerW int, tty bool) string {
	return colorDim("├"+strings.Repeat("─", innerW+4)+"┤", tty)
}

// ---------------------------------------------------------------------------------------
func (d *Display) boxBottom(innerW int, tty bool) string {
	return colorDim("╰"+strings.Repeat("─", innerW+4)+"╯", tty)
}

// ---------------------------------------------------------------------------------------
//
//	Formatting Helpers
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// formatSize formats a byte count as a human-readable string.
func formatSize(nbytes int64) string {
	if nbytes < 1024 {
		return fmt.Sprintf("%d B", nbytes)
	} else if nbytes < 1024*1024 {
		return fmt.Sprintf("%.1f KB", float64(nbytes)/1024)
	} else if nbytes < 1024*1024*1024 {
		return fmt.Sprintf("%.1f MB", float64(nbytes)/(1024*1024))
	} else if nbytes < 1024*1024*1024*1024 {
		return fmt.Sprintf("%.2f GB", float64(nbytes)/(1024*1024*1024))
	}
	return fmt.Sprintf("%.2f TB", float64(nbytes)/(1024*1024*1024*1024))
}

// ---------------------------------------------------------------------------------------
// formatFloat1 formats a float with 1 decimal place and comma-separated thousands.
// Replicates Python's "{:,.1f}" format.
func formatFloat1(f float64) string {
	s := fmt.Sprintf("%.1f", f)
	// Split on decimal point
	parts := strings.SplitN(s, ".", 2)
	integer := parts[0]
	decimal := ""
	if len(parts) > 1 {
		decimal = "." + parts[1]
	}

	// Handle negative
	negative := false
	if len(integer) > 0 && integer[0] == '-' {
		negative = true
		integer = integer[1:]
	}

	// Insert commas from right
	var result []byte
	for i, c := range integer {
		if i > 0 && (len(integer)-i)%3 == 0 {
			result = append(result, ',')
		}
		result = append(result, byte(c))
	}

	if negative {
		return "-" + string(result) + decimal
	}
	return string(result) + decimal
}

// ---------------------------------------------------------------------------------------
// formatTime formats seconds as h:mm:ss or m:ss.
func formatTime(seconds float64) string {
	if seconds < 0 {
		seconds = 0
	}
	s := int(seconds)
	if s < 3600 {
		return fmt.Sprintf("%d:%02d", s/60, s%60)
	}
	return fmt.Sprintf("%d:%02d:%02d", s/3600, (s%3600)/60, s%60)
}
