package main

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

const (
	runStateRunning   = "running"
	runStateCompleted = "completed"
	runStateFailed    = "failed"
	runStateSevere    = "severe"

	stepStatePending = "pending"
	stepStateRunning = "running"
	stepStateDone    = "done"
	stepStateFailed  = "failed"
	stepStateSkipped = "skipped"
)

type simulationRun struct {
	mu       sync.Mutex
	response SimulateResponse
	progress SimulationProgress
	doneAt   time.Time
}

func newSimulationRun(jobID string) *simulationRun {
	progress := SimulationProgress{
		Steps: []ProgressStep{
			{Key: "debug", Label: "디버그", State: stepStateRunning, Detail: "실행 중"},
			{Key: "simulation", Label: "시뮬레이션", State: stepStatePending, Detail: "대기 중"},
			{Key: "result", Label: "결과정리", State: stepStatePending, Detail: "대기 중"},
		},
	}

	return &simulationRun{
		response: SimulateResponse{
			JobID:    jobID,
			Code:     "RUNNING",
			State:    runStateRunning,
			Progress: cloneProgress(progress),
		},
		progress: progress,
	}
}

func (r *simulationRun) snapshot() SimulateResponse {
	r.mu.Lock()
	defer r.mu.Unlock()

	response := r.response
	response.Progress = cloneProgress(r.progress)
	return response
}

func (r *simulationRun) setStep(key string, state string, detail string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.setStepLocked(key, state, detail)
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) setDebugResult(debugResult *DebugResult) {
	errorCount, warningCount := countDebugRows(debugResult)
	detail := fmt.Sprintf("통과 (Error 없음, Warning %d개)", warningCount)
	state := stepStateDone

	if errorCount > 0 {
		detail = fmt.Sprintf("통과 (Error %d개, Warning %d개)", errorCount, warningCount)
	}

	if debugResult.Code == "SEVERE" {
		detail = fmt.Sprintf("실패 (Error %d개, Warning %d개)", errorCount, warningCount)
		state = stepStateFailed
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	r.response.Debug = debugResult
	r.setStepLocked("debug", state, detail)
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) setSimulationProgress(completed int, running int, total int, parallel int) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.progress.SimulationCompleted = completed
	r.progress.SimulationRunning = running
	r.progress.SimulationTotal = total
	r.progress.SimulationParallel = parallel

	state := stepStateRunning
	if completed == total && total > 0 {
		state = stepStateDone
	}

	r.setStepLocked("simulation", state, formatSimulationDetail(completed, running, total, parallel))
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) failStep(key string, detail string, debugResult *DebugResult) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.response.Code = "FAILED"
	r.response.State = runStateFailed
	r.response.Err = detail
	r.response.Debug = debugResult
	r.doneAt = time.Now()

	r.setStepLocked(key, stepStateFailed, detail)
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) finishSevere(debugResult *DebugResult, errText string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.response.Code = debugResult.Code
	r.response.State = runStateSevere
	r.response.Err = errText
	r.response.Debug = debugResult
	r.doneAt = time.Now()

	r.setStepLocked("simulation", stepStateSkipped, "디버그 오류로 실행하지 않음")
	r.setStepLocked("result", stepStateSkipped, "결과 없음")
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) finishCompleted(code string, debugResult *DebugResult, simData *SimData) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.response.Code = code
	r.response.State = runStateCompleted
	r.response.Debug = debugResult
	r.response.SimData = simData
	r.doneAt = time.Now()

	r.setStepLocked("result", stepStateDone, "정리 완료")
	r.response.Progress = cloneProgress(r.progress)
}

func (r *simulationRun) setStepLocked(key string, state string, detail string) {
	for idx := range r.progress.Steps {
		if r.progress.Steps[idx].Key == key {
			r.progress.Steps[idx].State = state
			r.progress.Steps[idx].Detail = detail
			return
		}
	}
}

func cloneProgress(progress SimulationProgress) *SimulationProgress {
	steps := make([]ProgressStep, len(progress.Steps))
	copy(steps, progress.Steps)

	return &SimulationProgress{
		Steps:               steps,
		SimulationCompleted: progress.SimulationCompleted,
		SimulationRunning:   progress.SimulationRunning,
		SimulationTotal:     progress.SimulationTotal,
		SimulationParallel:  progress.SimulationParallel,
	}
}

func countDebugRows(debugResult *DebugResult) (int, int) {
	if debugResult == nil {
		return 0, 0
	}

	errorCount := 0
	warningCount := 0

	for _, row := range debugResult.Report {
		importance := strings.ToUpper(strings.TrimSpace(fmt.Sprint(row["importance"])))
		switch importance {
		case "ERROR":
			errorCount++
		case "WARNING":
			warningCount++
		}
	}

	return errorCount, warningCount
}

func formatSimulationDetail(completed int, running int, total int, parallel int) string {
	if total <= 0 {
		return "대기 중"
	}

	if completed >= total {
		return fmt.Sprintf("%d/%d 완료", completed, total)
	}

	detail := fmt.Sprintf("%d/%d 완료", completed, total)
	if running > 0 {
		detail += fmt.Sprintf(": %d개 병렬 실행 중", running)
	}
	if parallel > 1 {
		detail += fmt.Sprintf(" (최대 %d개)", parallel)
	}

	return detail
}
