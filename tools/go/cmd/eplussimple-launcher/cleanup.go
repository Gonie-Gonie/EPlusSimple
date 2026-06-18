package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"eplussimple-go/internal/applog"
)

const completedJobRetention = 15 * time.Minute

func (a *App) addSimulationRun(run *simulationRun) {
	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()

	a.jobs[run.response.JobID] = run
}

func (a *App) getSimulationRun(jobID string) *simulationRun {
	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()

	return a.jobs[jobID]
}

func (a *App) forgetSimulationRunLater(jobID string) {
	time.Sleep(completedJobRetention)

	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()

	delete(a.jobs, jobID)
}

func (a *App) cleanupLauncherJobsDir() {
	jobsDir := filepath.Join(a.workDir, "logs", "launcher-jobs")
	if err := os.RemoveAll(jobsDir); err != nil {
		applog.WriteLine(a.logFile, fmt.Sprintf("Failed to remove stale launcher jobs directory %s: %s", jobsDir, err.Error()))
	}
}

func (a *App) cleanupJobDir(jobID string, jobDir string) {
	if err := os.RemoveAll(jobDir); err != nil {
		applog.WriteLine(a.logFile, fmt.Sprintf("Job %s: failed to remove job directory %s: %s", jobID, jobDir, err.Error()))
		return
	}

	jobsDir := filepath.Dir(jobDir)
	if err := removeDirIfEmpty(jobsDir); err != nil {
		applog.WriteLine(a.logFile, fmt.Sprintf("Job %s: failed to remove empty jobs directory %s: %s", jobID, jobsDir, err.Error()))
	}
}

func removeDirIfEmpty(dir string) error {
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}

	if len(entries) != 0 {
		return nil
	}

	if err := os.Remove(dir); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}

	return nil
}
