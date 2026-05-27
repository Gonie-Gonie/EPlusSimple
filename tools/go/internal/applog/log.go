package applog

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

func ExecutableDir() (string, error) {
	exePath, err := os.Executable()
	if err != nil {
		return "", err
	}

	return filepath.Dir(exePath), nil
}

func Open(rootDir string, filename string) (*os.File, string, error) {
	logDir := filepath.Join(rootDir, "logs")

	if err := os.MkdirAll(logDir, 0755); err != nil {
		return nil, "", fmt.Errorf("failed to create log directory: %w", err)
	}

	logPath := filepath.Join(logDir, filename)

	file, err := os.Create(logPath)
	if err != nil {
		return nil, "", fmt.Errorf("failed to create log file: %w", err)
	}

	_, _ = fmt.Fprintf(file, "============================================================================\n")
	_, _ = fmt.Fprintf(file, " %s\n", filename)
	_, _ = fmt.Fprintf(file, "============================================================================\n")
	_, _ = fmt.Fprintf(file, "Started: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	_, _ = fmt.Fprintf(file, "Root   : %s\n", rootDir)
	_, _ = fmt.Fprintf(file, "Log    : %s\n", logPath)
	_, _ = fmt.Fprintf(file, "============================================================================\n\n")

	return file, logPath, nil
}

func WriteLine(file *os.File, message string) {
	if file == nil {
		return
	}

	_, _ = fmt.Fprintf(
		file,
		"[%s] %s\n",
		time.Now().Format("2006-01-02 15:04:05"),
		message,
	)
}

func RedirectCommand(cmd *exec.Cmd, logFile *os.File, mirrorToConsole bool) {
	if logFile == nil {
		return
	}

	if mirrorToConsole {
		cmd.Stdout = io.MultiWriter(os.Stdout, logFile)
		cmd.Stderr = io.MultiWriter(os.Stderr, logFile)
	} else {
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}
}
