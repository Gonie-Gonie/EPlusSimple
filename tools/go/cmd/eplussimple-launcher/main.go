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

	"eplussimple-go/internal/applog"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

const (
	pythonFolderName = "PythonV3-12-7"
	moduleName       = "launcher"
	logFileName      = "launcher.log"

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
	logPath    string
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

	applog.WriteLine(a.logFile, "Flask backend is ready: "+serverURL.String())
}

func (a *App) shutdown(ctx context.Context) {
	applog.WriteLine(a.logFile, "Launcher shutdown requested.")
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
				"\n\nCheck logs\\launcher.log for Python-side errors.",
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
		applog.WriteLine(a.logFile, "Reverse proxy error: "+err.Error())

		http.Error(
			w,
			"EPlusSimple launcher server is not available: "+err.Error(),
			http.StatusBadGateway,
		)
	}

	proxy.ServeHTTP(w, r)
}

func (a *App) startFlask(port int) error {
	logFile, logPath, err := applog.Open(a.workDir, logFileName)
	if err != nil {
		return err
	}

	a.logFile = logFile
	a.logPath = logPath

	pythonExe := filepath.Join(a.workDir, "runtime", pythonFolderName, "python.exe")
	if _, err := os.Stat(pythonExe); err != nil {
		applog.WriteLine(logFile, "Python executable not found: "+pythonExe)
		_ = logFile.Close()
		a.logFile = nil
		return fmt.Errorf("Python executable not found: %s", pythonExe)
	}

	applog.WriteLine(logFile, "Starting Flask launcher backend.")
	applog.WriteLine(logFile, "Python executable: "+pythonExe)
	applog.WriteLine(logFile, "Flask host: 127.0.0.1")
	applog.WriteLine(logFile, fmt.Sprintf("Flask port: %d", port))
	applog.WriteLine(logFile, "Log path: "+logPath)

	cmd := exec.Command(pythonExe, "-s", "-m", moduleName)
	cmd.Dir = a.workDir
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

	// Keep Flask stdout/stderr in logs/launcher.log.
	applog.RedirectCommand(cmd, logFile, false)

	if err := cmd.Start(); err != nil {
		applog.WriteLine(logFile, "Failed to start Flask server: "+err.Error())
		_ = logFile.Close()
		a.logFile = nil
		return fmt.Errorf("failed to start Flask server: %w", err)
	}

	a.cmd = cmd
	applog.WriteLine(logFile, fmt.Sprintf("Flask process started. PID: %d", cmd.Process.Pid))

	return nil
}

func (a *App) stopFlask() {
	if a.cmd != nil && a.cmd.Process != nil {
		applog.WriteLine(a.logFile, "Stopping Flask process.")
		_ = a.cmd.Process.Kill()
		_, _ = a.cmd.Process.Wait()
		a.cmd = nil
	}

	if a.logFile != nil {
		applog.WriteLine(a.logFile, "Closing launcher log.")
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
