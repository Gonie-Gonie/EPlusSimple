package main

import (
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

const (
	pythonFolderName = "PythonV3-12-7"
	moduleName       = "launcher"
	serverAddr       = "127.0.0.1:5000"
	serverURL        = "http://127.0.0.1:5000"
)

func main() {
	fmt.Println("==============================")
	fmt.Println("[1/4] Changing to working directory...")

	exePath, err := os.Executable()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to locate executable path: %v\n", err)
		os.Exit(1)
	}

	workDir := filepath.Dir(exePath)
	pythonExe := filepath.Join(workDir, "runtime", pythonFolderName, "python.exe")

	if _, err := os.Stat(pythonExe); err != nil {
		fmt.Fprintf(os.Stderr, "Python executable not found: %s\n", pythonExe)
		os.Exit(1)
	}

	fmt.Println("[2/4] Starting Flask server...")

	cmd := exec.Command(pythonExe, "-m", moduleName)
	cmd.Dir = workDir

	// Keep server process attached to this console.
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Keep Python output encoding stable.
	cmd.Env = append(os.Environ(),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
	)

	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start Flask server: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("[3/4] Waiting for the server to start...")
	if waitForTCP(serverAddr, 10*time.Second) {
		fmt.Printf("[4/4] Launching the web browser: %s\n", serverURL)
		if err := openBrowser(serverURL); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to launch browser: %v\n", err)
		}
	} else {
		fmt.Fprintf(os.Stderr, "Server did not become ready within the timeout: %s\n", serverAddr)
		fmt.Fprintf(os.Stderr, "The server process may still be starting. Open manually: %s\n", serverURL)
	}

	fmt.Println("The server is now running. To stop it, close this window or press Ctrl+C.")
	fmt.Println("==============================")

	err = cmd.Wait()

	fmt.Println()
	fmt.Println("==============================")
	fmt.Println("The server process has ended.")
	fmt.Println("If it was unexpected, check for error messages above.")

	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(exitErr.ExitCode())
		}

		fmt.Fprintf(os.Stderr, "Server process ended with error: %v\n", err)
		os.Exit(1)
	}
}

func waitForTCP(addr string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)

	for time.Now().Before(deadline) {
		conn, err := net.DialTimeout("tcp", addr, 300*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			return true
		}

		time.Sleep(200 * time.Millisecond)
	}

	return false
}

func openBrowser(url string) error {
	// Windows equivalent of:
	// start "" "http://127.0.0.1:5000"
	return exec.Command("cmd", "/c", "start", "", url).Start()
}
