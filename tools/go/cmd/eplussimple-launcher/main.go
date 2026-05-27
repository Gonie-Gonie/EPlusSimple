package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

const (
	pythonFolderName = "PythonV3-12-7"
	moduleName       = "launcher"

	envHost  = "EPLUSSIMPLE_LAUNCHER_HOST"
	envPort  = "EPLUSSIMPLE_LAUNCHER_PORT"
	envDebug = "EPLUSSIMPLE_LAUNCHER_DEBUG"

	createNoWindow = 0x08000000
)

type App struct {
	ctx        context.Context
	workDir    string
	serverURL  *url.URL
	cmd        *exec.Cmd
	logFile    *os.File
	ready      chan struct{}
	startupErr error
}

func main() {
	app := &App{
		ready: make(chan struct{}),
	}

	err := wails.Run(&options.App{
		Title:     "EPlusSimple Launcher",
		Width:     1200,
		Height:    820,
		MinWidth:  900,
		MinHeight: 650,

		AssetServer: &assetserver.Options{
			Assets:  nil,
			Handler: app,
		},

		OnStartup:  app.startup,
		OnShutdown: app.shutdown,

		EnableDefaultContextMenu: false,
	})

	if err != nil {
		log.Fatal(err)
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	defer close(a.ready)

	workDir, err := getExecutableDir()
	if err != nil {
		a.startupErr = err
		return
	}
	a.workDir = workDir

	port, err := getFreePort()
	if err != nil {
		a.startupErr = err
		return
	}

	serverURL, err := url.Parse(fmt.Sprintf("http://127.0.0.1:%d", port))
	if err != nil {
		a.startupErr = err
		return
	}
	a.serverURL = serverURL

	if err := a.startFlask(port); err != nil {
		a.startupErr = err
		return
	}

	if err := waitForHTTP(serverURL.String()+"/", 20*time.Second); err != nil {
		a.stopFlask()
		a.startupErr = err
		return
	}
}

func (a *App) shutdown(ctx context.Context) {
	a.stopFlask()
}

func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	select {
	case <-a.ready:
		// continue
	case <-time.After(30 * time.Second):
		http.Error(
			w,
			"EPlusSimple launcher is still starting. Please close and reopen the launcher if this continues.",
			http.StatusServiceUnavailable,
		)
		return
	}

	if a.startupErr != nil {
		http.Error(
			w,
			"EPlusSimple launcher failed to start.\n\n"+
				a.startupErr.Error()+
				"\n\nCheck logs\\eplussimple-launcher.log for Python-side errors.",
			http.StatusInternalServerError,
		)
		return
	}

	if a.serverURL == nil {
		http.Error(w, "Flask server URL is not initialized.", http.StatusServiceUnavailable)
		return
	}

	if (r.Method == http.MethodGet || r.Method == http.MethodHead) && r.URL.Path == "/" {
		http.Redirect(w, r, a.serverURL.String()+"/", http.StatusFound)
		return
	}

	proxy := httputil.NewSingleHostReverseProxy(a.serverURL)

	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)

		req.URL.Scheme = a.serverURL.Scheme
		req.URL.Host = a.serverURL.Host
		req.Host = a.serverURL.Host

		req.Header.Set("X-Forwarded-Host", r.Host)
		req.Header.Set("X-Forwarded-Proto", "http")
	}

	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		http.Error(
			w,
			"EPlusSimple launcher server is not available: "+err.Error(),
			http.StatusBadGateway,
		)
	}

	proxy.ServeHTTP(w, r)
}

func (a *App) startFlask(port int) error {
	pythonExe := filepath.Join(a.workDir, "runtime", pythonFolderName, "python.exe")

	if _, err := os.Stat(pythonExe); err != nil {
		return fmt.Errorf("Python executable not found: %s", pythonExe)
	}

	logDir := filepath.Join(a.workDir, "logs")
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return fmt.Errorf("failed to create log directory: %w", err)
	}

	logPath := filepath.Join(logDir, "eplussimple-launcher.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to open launcher log: %w", err)
	}
	a.logFile = logFile

	cmd := exec.Command(pythonExe, "-s", "-m", moduleName)
	cmd.Dir = a.workDir

	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Stdin = nil

	cmd.Env = append(
		os.Environ(),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
		"PYTHONNOUSERSITE=1",
		envHost+"=127.0.0.1",
		fmt.Sprintf("%s=%d", envPort, port),
		envDebug+"=0",
	)

	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: createNoWindow,
	}

	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		a.logFile = nil
		return fmt.Errorf("failed to start Flask server: %w", err)
	}

	a.cmd = cmd
	return nil
}

func (a *App) stopFlask() {
	if a.cmd != nil && a.cmd.Process != nil {
		_ = a.cmd.Process.Kill()
		_, _ = a.cmd.Process.Wait()
		a.cmd = nil
	}

	if a.logFile != nil {
		_ = a.logFile.Close()
		a.logFile = nil
	}
}

func getExecutableDir() (string, error) {
	exePath, err := os.Executable()
	if err != nil {
		return "", err
	}

	return filepath.Dir(exePath), nil
}

func getFreePort() (int, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer listener.Close()

	addr, ok := listener.Addr().(*net.TCPAddr)
	if !ok {
		return 0, errors.New("failed to resolve TCP address")
	}

	return addr.Port, nil
}

func waitForHTTP(targetURL string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)

	client := &http.Client{
		Timeout: 800 * time.Millisecond,
	}

	var lastErr error

	for time.Now().Before(deadline) {
		resp, err := client.Get(targetURL)
		if err == nil {
			_ = resp.Body.Close()

			if resp.StatusCode < 500 {
				return nil
			}

			lastErr = fmt.Errorf("server returned status code %d", resp.StatusCode)
		} else {
			lastErr = err
		}

		time.Sleep(300 * time.Millisecond)
	}

	if lastErr == nil {
		lastErr = errors.New("timeout")
	}

	return lastErr
}
