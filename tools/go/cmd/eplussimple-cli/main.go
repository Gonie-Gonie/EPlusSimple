package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"eplussimple-go/internal/applog"
)

const (
	pythonFolderName = "PythonV3-12-7"
	moduleName       = "epsimple"
	logFileName      = "cli.log"
)

func main() {
	workDir, err := getExecutableDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to locate executable path: %v\n", err)
		os.Exit(1)
	}

	logFile, logPath, err := applog.Open(workDir, logFileName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create CLI log file: %v\n", err)
		os.Exit(1)
	}
	defer logFile.Close()

	applog.WriteLine(logFile, "Starting EPlusSimple CLI.")
	applog.WriteLine(logFile, "Working directory: "+workDir)
	applog.WriteLine(logFile, "Log file: "+logPath)

	pythonExe := filepath.Join(workDir, "runtime", pythonFolderName, "python.exe")
	if _, err := os.Stat(pythonExe); err != nil {
		applog.WriteLine(logFile, "Python executable not found: "+pythonExe)
		fmt.Fprintf(os.Stderr, "Python executable not found: %s\n", pythonExe)
		fmt.Fprintf(os.Stderr, "Log: %s\n", logPath)
		os.Exit(1)
	}

	args := append([]string{"-s", "-m", moduleName}, os.Args[1:]...)

	applog.WriteLine(logFile, "Python executable: "+pythonExe)
	applog.WriteLine(logFile, fmt.Sprintf("Python arguments: %v", args))

	cmd := exec.Command(pythonExe, args...)
	cmd.Dir = workDir
	cmd.Stdin = os.Stdin

	cmd.Env = append(
		os.Environ(),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
		"PYTHONNOUSERSITE=1",
	)

	// Keep Python stdout/stderr in logs/cli.log.
	// The console stays concise.
	applog.RedirectCommand(cmd, logFile, false)

	err = cmd.Run()

	if err != nil {
		applog.WriteLine(logFile, "EPlusSimple CLI failed: "+err.Error())

		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			fmt.Fprintf(os.Stderr, "EPlusSimple CLI failed. Exit code: %d\n", exitErr.ExitCode())
			fmt.Fprintf(os.Stderr, "Log: %s\n", logPath)
			os.Exit(exitErr.ExitCode())
		}

		fmt.Fprintf(os.Stderr, "Failed to execute Python module: %v\n", err)
		fmt.Fprintf(os.Stderr, "Log: %s\n", logPath)
		os.Exit(1)
	}

	applog.WriteLine(logFile, "EPlusSimple CLI finished successfully.")
	fmt.Printf("EPlusSimple CLI finished. Log: %s\n", logPath)
}

func getExecutableDir() (string, error) {
	exePath, err := os.Executable()
	if err != nil {
		return "", err
	}

	return filepath.Dir(exePath), nil
}
