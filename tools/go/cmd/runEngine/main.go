package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)

func main() {
	exePath, err := os.Executable()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to locate executable path: %v\n", err)
		os.Exit(1)
	}

	batchDir := filepath.Dir(exePath)

	pythonExe := filepath.Join(batchDir, "runtime", "PythonV3-12-7", "python.exe")
	moduleName := "epsimple"
	logFile := filepath.Join(batchDir, "log.log")

	if _, err := os.Stat(pythonExe); err != nil {
		fmt.Fprintf(os.Stderr, "Python executable not found: %s\n", pythonExe)
		os.Exit(1)
	}

	// Delete existing log file.
	if err := os.Remove(logFile); err != nil && !errors.Is(err, os.ErrNotExist) {
		fmt.Fprintf(os.Stderr, "Failed to delete existing log file: %v\n", err)
		os.Exit(1)
	}

	log, err := os.Create(logFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create log file: %v\n", err)
		os.Exit(1)
	}
	defer log.Close()

	// Equivalent to:
	// runtime\PythonV3-12-7\python.exe -m epsimple %* > log.log 2>&1
	args := append([]string{"-m", moduleName}, os.Args[1:]...)

	cmd := exec.Command(pythonExe, args...)
	cmd.Dir = batchDir
	cmd.Stdout = log
	cmd.Stderr = log

	// Keep Python output encoding stable when logs contain Korean text.
	cmd.Env = append(os.Environ(),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
	)

	err = cmd.Run()

	fmt.Println("Script execution finished.")

	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(exitErr.ExitCode())
		}

		fmt.Fprintf(os.Stderr, "Failed to execute Python module: %v\n", err)
		os.Exit(1)
	}
}
