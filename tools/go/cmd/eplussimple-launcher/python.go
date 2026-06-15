package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"

	"eplussimple-go/internal/applog"
)

type PythonRunner struct {
	RootDir string
	LogFile *os.File
}

func (p PythonRunner) Debug(ctx context.Context, jobDir string, files []UploadedFile, workers int) (*DebugResult, error) {
	if workers < 1 {
		workers = 1
	}

	args := []string{"-s", "-m", "epsimple", "debug", "-w", fmt.Sprint(workers), "-i"}

	for _, file := range files {
		args = append(args, file.Path)
	}

	stdout, _, err := p.run(ctx, jobDir, args...)
	if err != nil {
		return nil, err
	}

	var result DebugResult
	if err := json.Unmarshal(stdout, &result); err != nil {
		return nil, fmt.Errorf("failed to decode debug CLI JSON: %w", err)
	}

	if result.Code == "" {
		return nil, errors.New("debug CLI response did not include code")
	}

	return &result, nil
}

func (p PythonRunner) RunExcel(ctx context.Context, jobDir string, outputDir string, file UploadedFile, label string) (json.RawMessage, error) {
	outputPath := filepath.Join(outputDir, label+".grr")

	args := []string{
		"-s",
		"-m",
		"epsimple",
		"run",
		"-i",
		file.Path,
		"-o",
		outputPath,
	}

	if _, _, err := p.run(ctx, jobDir, args...); err != nil {
		return nil, err
	}

	data, err := os.ReadFile(outputPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read simulation output %s: %w", outputPath, err)
	}

	data = bytes.TrimPrefix(data, []byte("\xef\xbb\xbf"))

	var raw json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("simulation output is not valid JSON: %w", err)
	}

	return raw, nil
}

func (p PythonRunner) run(ctx context.Context, jobDir string, args ...string) ([]byte, []byte, error) {
	pythonExe := filepath.Join(p.RootDir, "runtime", pythonFolderName, "python.exe")
	if _, err := os.Stat(pythonExe); err != nil {
		return nil, nil, fmt.Errorf("Python executable not found: %s", pythonExe)
	}

	jobLogPath := filepath.Join(jobDir, "worker.log")
	jobLog, err := os.OpenFile(jobLogPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to open worker log: %w", err)
	}
	defer jobLog.Close()

	cmd := exec.CommandContext(ctx, pythonExe, args...)
	cmd.Dir = p.RootDir
	cmd.Stdin = nil

	cmd.Env = p.environment()

	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: createNoWindow,
	}

	var stdoutBuffer bytes.Buffer
	var stderrBuffer bytes.Buffer

	stdoutWriter := io.MultiWriter(&stdoutBuffer, jobLog)
	stderrWriter := io.MultiWriter(&stderrBuffer, jobLog)

	if p.LogFile != nil {
		stdoutWriter = io.MultiWriter(&stdoutBuffer, jobLog, p.LogFile)
		stderrWriter = io.MultiWriter(&stderrBuffer, jobLog, p.LogFile)
	}

	cmd.Stdout = stdoutWriter
	cmd.Stderr = stderrWriter

	applog.WriteLine(p.LogFile, "Python command: "+pythonExe+" "+strings.Join(args, " "))

	err = cmd.Run()

	stdout := stdoutBuffer.Bytes()
	stderr := stderrBuffer.Bytes()

	if err != nil {
		stderrText := strings.TrimSpace(string(stderr))
		if stderrText != "" {
			return stdout, stderr, fmt.Errorf("%w: %s", err, stderrText)
		}
		return stdout, stderr, err
	}

	return stdout, stderr, nil
}

func (p PythonRunner) environment() []string {
	runtimeDir := filepath.Join(p.RootDir, "runtime")
	energyPlusDir := filepath.Join(runtimeDir, "EnergyPlusV24-2-0")
	weatherDir := filepath.Join(runtimeDir, "Weather")
	tmyDir := filepath.Join(weatherDir, "TMY")

	env := append(
		os.Environ(),
		"PYTHONUTF8=1",
		"PYTHONIOENCODING=utf-8",
		"PYTHONNOUSERSITE=1",
		"EPSIMPLE_RUNTIME_DIR="+runtimeDir,
		"IDRAGON_RUNTIME_DIR="+runtimeDir,
		"IDRAGON_ENERGYPLUS_DIR="+energyPlusDir,
		"ENERGYPLUS_DIR="+energyPlusDir,
		"ENERGYPLUS_EXE="+filepath.Join(energyPlusDir, "energyplus.exe"),
		"EPSIMPLE_WEATHER_DIR="+weatherDir,
		"EPSIMPLE_TMY_DIR="+tmyDir,
	)

	env = append(env, "PATH="+energyPlusDir+";"+os.Getenv("PATH"))

	return env
}
