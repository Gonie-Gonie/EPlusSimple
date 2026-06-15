package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"time"

	"eplussimple-go/internal/applog"
)

const maxUploadSize = 512 << 20

type simulationJob struct {
	Index int
	File  UploadedFile
	Label string
}

func (a *App) handleSimulate(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)

	reader, err := r.MultipartReader()
	if err != nil {
		writeJSON(w, http.StatusBadRequest, SimulateResponse{
			Code: "FAILED",
			Err:  "failed to read multipart upload: " + err.Error(),
		})
		return
	}

	jobID, err := newJobID()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, SimulateResponse{
			Code: "FAILED",
			Err:  "failed to create job id: " + err.Error(),
		})
		return
	}

	jobDir := filepath.Join(a.workDir, "logs", "launcher-jobs", jobID)
	inputDir := filepath.Join(jobDir, "input")
	outputDir := filepath.Join(jobDir, "output")
	started := false
	defer func() {
		if !started {
			a.cleanupJobDir(jobID, jobDir)
		}
	}()

	if err := os.MkdirAll(inputDir, 0755); err != nil {
		writeJSON(w, http.StatusInternalServerError, SimulateResponse{
			JobID: jobID,
			Code:  "FAILED",
			Err:   "failed to create job input directory: " + err.Error(),
		})
		return
	}

	if err := os.MkdirAll(outputDir, 0755); err != nil {
		writeJSON(w, http.StatusInternalServerError, SimulateResponse{
			JobID: jobID,
			Code:  "FAILED",
			Err:   "failed to create job output directory: " + err.Error(),
		})
		return
	}

	beforeFile, afterFiles, err := saveUploadedSimulationFiles(reader, inputDir)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, SimulateResponse{
			JobID: jobID,
			Code:  "FAILED",
			Err:   err.Error(),
		})
		return
	}

	allFiles := append([]UploadedFile{beforeFile}, afterFiles...)
	run := newSimulationRun(jobID)
	a.addSimulationRun(run)

	ctx := a.ctx
	if ctx == nil {
		ctx = context.Background()
	}

	go a.runSimulation(ctx, run, jobDir, outputDir, beforeFile, afterFiles, allFiles)
	started = true

	writeJSON(w, http.StatusAccepted, run.snapshot())
}

func (a *App) handleSimulationStatus(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimSpace(r.URL.Query().Get("job_id"))
	if jobID == "" {
		writeJSON(w, http.StatusBadRequest, SimulateResponse{
			Code:  "FAILED",
			State: runStateFailed,
			Err:   "job_id is required",
		})
		return
	}

	run := a.getSimulationRun(jobID)
	if run == nil {
		writeJSON(w, http.StatusNotFound, SimulateResponse{
			JobID: jobID,
			Code:  "FAILED",
			State: runStateFailed,
			Err:   "simulation job was not found",
		})
		return
	}

	writeJSON(w, http.StatusOK, run.snapshot())
}

func (a *App) runSimulation(ctx context.Context, run *simulationRun, jobDir string, outputDir string, beforeFile UploadedFile, afterFiles []UploadedFile, allFiles []UploadedFile) {
	jobID := run.response.JobID

	defer func() {
		a.cleanupJobDir(jobID, jobDir)
		go a.forgetSimulationRunLater(jobID)
	}()

	debugWorkers := maxParallelWorkers(len(allFiles))
	run.setStep("debug", stepStateRunning, fmt.Sprintf("실행 중 (최대 %d개 병렬)", debugWorkers))
	applog.WriteLine(a.logFile, fmt.Sprintf("Job %s: starting debug for %d file(s) with %d worker(s).", jobID, len(allFiles), debugWorkers))

	debugResult, err := a.python.Debug(ctx, jobDir, allFiles, debugWorkers)
	if err != nil {
		run.failStep("debug", "debug CLI failed: "+err.Error(), nil)
		return
	}

	run.setDebugResult(debugResult)

	if debugResult.Code == "SEVERE" {
		applog.WriteLine(a.logFile, fmt.Sprintf("Job %s: severe debug issues found. Simulation skipped.", jobID))
		run.finishSevere(debugResult, "심각한 오류가 발견되어 시뮬레이션을 실행하지 않았습니다.")
		return
	}

	applog.WriteLine(a.logFile, fmt.Sprintf("Job %s: debug finished with code %s. Starting simulation.", jobID, debugResult.Code))

	jobs := make([]simulationJob, 0, 1+len(afterFiles))
	jobs = append(jobs, simulationJob{
		Index: 0,
		File:  beforeFile,
		Label: "before",
	})

	for idx, afterFile := range afterFiles {
		jobs = append(jobs, simulationJob{
			Index: idx + 1,
			File:  afterFile,
			Label: fmt.Sprintf("after_%03d", idx+1),
		})
	}

	run.setSimulationProgress(0, 0, len(jobs), maxParallelWorkers(len(jobs)))

	results, err := a.runSimulationJobs(ctx, jobDir, outputDir, jobs, run.setSimulationProgress)
	if err != nil {
		run.failStep("simulation", err.Error(), debugResult)
		return
	}

	run.setStep("result", stepStateRunning, "결과 정리 중")

	beforeResult := results[0]
	afterNames := make([]string, 0)
	afterResults := make([]json.RawMessage, 0)

	if len(afterFiles) == 0 {
		afterNames = append(afterNames, beforeFile.OriginalName+" (후 파일 미지정)")
		afterResults = append(afterResults, beforeResult)
	} else {
		for idx, afterFile := range afterFiles {
			afterNames = append(afterNames, afterFile.OriginalName)
			afterResults = append(afterResults, results[idx+1])
		}
	}

	run.finishCompleted(debugResult.Code, debugResult, &SimData{
		FilenameBefore: beforeFile.OriginalName,
		FilenamesAfter: afterNames,
		Before:         beforeResult,
		Afters:         afterResults,
	})
}

func (a *App) runSimulationJobs(ctx context.Context, jobDir string, outputDir string, jobs []simulationJob, updateProgress func(completed int, running int, total int, parallel int)) ([]json.RawMessage, error) {
	if len(jobs) == 0 {
		return nil, fmt.Errorf("no simulation jobs were requested")
	}

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	results := make([]json.RawMessage, len(jobs))
	errCh := make(chan error, len(jobs))
	parallel := maxParallelWorkers(len(jobs))
	sem := make(chan struct{}, parallel)

	var wg sync.WaitGroup
	var progressMu sync.Mutex
	completed := 0
	running := 0

	emitProgress := func() {
		if updateProgress != nil {
			updateProgress(completed, running, len(jobs), parallel)
		}
	}

	for _, job := range jobs {
		job := job
		wg.Add(1)

		go func() {
			defer wg.Done()

			select {
			case sem <- struct{}{}:
				defer func() { <-sem }()
			case <-ctx.Done():
				errCh <- ctx.Err()
				return
			}

			applog.WriteLine(a.logFile, fmt.Sprintf("Job simulation started: %s (%s)", job.Label, job.File.OriginalName))

			progressMu.Lock()
			running++
			emitProgress()
			progressMu.Unlock()

			success := false
			defer func() {
				progressMu.Lock()
				running--
				if success {
					completed++
				}
				emitProgress()
				progressMu.Unlock()
			}()

			result, err := a.python.RunExcel(ctx, jobDir, outputDir, job.File, job.Label)
			if err != nil {
				cancel()
				errCh <- fmt.Errorf("simulation failed for %s: %w", job.File.OriginalName, err)
				return
			}

			results[job.Index] = result
			success = true
			applog.WriteLine(a.logFile, fmt.Sprintf("Job simulation finished: %s (%s)", job.Label, job.File.OriginalName))
		}()
	}

	wg.Wait()
	close(errCh)

	var firstErr error
	for err := range errCh {
		if err == nil {
			continue
		}
		if firstErr == nil || errors.Is(firstErr, context.Canceled) {
			firstErr = err
		}
	}

	if firstErr != nil {
		return nil, firstErr
	}

	return results, nil
}

func minInt(a int, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxParallelWorkers(total int) int {
	if total < 1 {
		return 1
	}
	return minInt(maxParallelSimulations(), total)
}

func maxParallelSimulations() int {
	n := runtime.NumCPU() / 2
	if n < 1 {
		return 1
	}
	return n
}

func saveUploadedSimulationFiles(reader *multipart.Reader, inputDir string) (UploadedFile, []UploadedFile, error) {
	var beforeFile UploadedFile
	hasBefore := false

	afterFiles := make([]UploadedFile, 0)
	afterIndex := 0

	for {
		part, err := reader.NextPart()
		if err == io.EOF {
			break
		}
		if err != nil {
			return UploadedFile{}, nil, fmt.Errorf("failed to read uploaded multipart data: %w", err)
		}

		formName := part.FormName()
		fileName := part.FileName()

		if fileName == "" {
			_ = part.Close()
			continue
		}

		switch formName {
		case "file_before":
			if hasBefore {
				_ = part.Close()
				return UploadedFile{}, nil, fmt.Errorf("multiple '리모델링 전' files were uploaded")
			}

			uploaded, err := saveUploadedPart(part, inputDir, "before")
			if err != nil {
				return UploadedFile{}, nil, err
			}

			beforeFile = uploaded
			hasBefore = true

		case "file_after":
			afterIndex++
			uploaded, err := saveUploadedPart(part, inputDir, fmt.Sprintf("after_%03d", afterIndex))
			if err != nil {
				return UploadedFile{}, nil, err
			}

			afterFiles = append(afterFiles, uploaded)

		default:
			_ = part.Close()
		}
	}

	if !hasBefore {
		return UploadedFile{}, nil, fmt.Errorf("'리모델링 전' 파일이 선택되지 않았습니다")
	}

	return beforeFile, afterFiles, nil
}

func saveUploadedPart(part *multipart.Part, inputDir string, prefix string) (UploadedFile, error) {
	defer part.Close()

	originalName := filepath.Base(part.FileName())
	if originalName == "" {
		return UploadedFile{}, fmt.Errorf("empty upload file")
	}

	extension := strings.ToLower(filepath.Ext(originalName))

	switch extension {
	case ".xlsx", ".xlsm", ".xls":
		// ok
	default:
		return UploadedFile{}, fmt.Errorf("unsupported file extension: %s", originalName)
	}

	filename := prefix + "_" + sanitizeFilename(originalName)
	targetPath := filepath.Join(inputDir, filename)
	tmpPath := targetPath + ".uploading"

	dst, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		return UploadedFile{}, fmt.Errorf("failed to create uploaded file %s: %w", tmpPath, err)
	}

	buffer := make([]byte, 1024*1024)
	_, copyErr := io.CopyBuffer(dst, part, buffer)
	syncErr := dst.Sync()
	closeErr := dst.Close()

	if copyErr != nil {
		_ = os.Remove(tmpPath)
		return UploadedFile{}, fmt.Errorf("failed to save uploaded file %s: %w", originalName, copyErr)
	}

	if syncErr != nil {
		_ = os.Remove(tmpPath)
		return UploadedFile{}, fmt.Errorf("failed to flush uploaded file %s: %w", originalName, syncErr)
	}

	if closeErr != nil {
		_ = os.Remove(tmpPath)
		return UploadedFile{}, fmt.Errorf("failed to close uploaded file %s: %w", originalName, closeErr)
	}

	if err := os.Rename(tmpPath, targetPath); err != nil {
		_ = os.Remove(tmpPath)
		return UploadedFile{}, fmt.Errorf("failed to finalize uploaded file %s: %w", originalName, err)
	}

	stat, err := os.Stat(targetPath)
	if err != nil {
		return UploadedFile{}, fmt.Errorf("failed to stat uploaded file %s: %w", originalName, err)
	}

	return UploadedFile{
		FieldName:    prefix,
		FileName:     filename,
		OriginalName: originalName,
		Path:         targetPath,
		Size:         stat.Size(),
	}, nil
}

var invalidFilenameChars = regexp.MustCompile(`[<>:"/\\|?*\x00-\x1f]+`)

func sanitizeFilename(name string) string {
	name = filepath.Base(name)
	name = invalidFilenameChars.ReplaceAllString(name, "_")
	name = strings.TrimSpace(name)

	if name == "" {
		return "input.xlsx"
	}

	return name
}

func newJobID() (string, error) {
	var randomBytes [4]byte
	if _, err := rand.Read(randomBytes[:]); err != nil {
		return "", err
	}

	return time.Now().Format("20060102-150405") + "-" + hex.EncodeToString(randomBytes[:]), nil
}
