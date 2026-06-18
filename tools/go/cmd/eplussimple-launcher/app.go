package main

import (
	"context"
	"net/http"
	"os"
	"sync"

	"eplussimple-go/internal/applog"
)

type App struct {
	ctx        context.Context
	workDir    string
	logFile    *os.File
	logPath    string
	ready      chan struct{}
	startupErr error

	frontend http.Handler
	python   PythonRunner

	jobsMu sync.Mutex
	jobs   map[string]*simulationRun
}

func NewApp() *App {
	return &App{
		ready: make(chan struct{}),
		jobs:  make(map[string]*simulationRun),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	defer close(a.ready)

	workDir, err := applog.ExecutableDir()
	if err != nil {
		a.startupErr = err
		return
	}
	a.workDir = workDir

	logFile, logPath, err := applog.Open(workDir, logFileName)
	if err != nil {
		a.startupErr = err
		return
	}
	a.logFile = logFile
	a.logPath = logPath

	frontend, err := newFrontendHandler()
	if err != nil {
		a.startupErr = err
		return
	}
	a.frontend = frontend

	a.python = PythonRunner{
		RootDir: workDir,
		LogFile: logFile,
	}

	applog.WriteLine(a.logFile, "Go launcher started.")
	applog.WriteLine(a.logFile, "Working directory: "+a.workDir)
	applog.WriteLine(a.logFile, "Log path: "+a.logPath)

	a.cleanupLauncherJobsDir()
}

func (a *App) shutdown(ctx context.Context) {
	applog.WriteLine(a.logFile, "Launcher shutdown requested.")

	if a.logFile != nil {
		applog.WriteLine(a.logFile, "Closing launcher log.")
		_ = a.logFile.Close()
		a.logFile = nil
	}
}
