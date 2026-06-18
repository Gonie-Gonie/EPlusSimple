package main

import "encoding/json"

type UploadedFile struct {
	FieldName    string `json:"field_name"`
	FileName     string `json:"filename"`
	OriginalName string `json:"original_name"`
	Path         string `json:"path"`
	Size         int64  `json:"size"`
}

type DebugResult struct {
	Code   string           `json:"code"`
	Report []map[string]any `json:"report"`
	Files  []map[string]any `json:"files"`
}

type SimData struct {
	FilenameBefore string            `json:"filename_before"`
	FilenamesAfter []string          `json:"filenames_after"`
	Before         json.RawMessage   `json:"before"`
	Afters         []json.RawMessage `json:"afters"`
}

type ProgressStep struct {
	Key    string `json:"key"`
	Label  string `json:"label"`
	State  string `json:"state"`
	Detail string `json:"detail,omitempty"`
}

type SimulationProgress struct {
	Steps               []ProgressStep `json:"steps"`
	SimulationCompleted int            `json:"simulation_completed"`
	SimulationRunning   int            `json:"simulation_running"`
	SimulationTotal     int            `json:"simulation_total"`
	SimulationParallel  int            `json:"simulation_parallel"`
}

type SimulateResponse struct {
	JobID    string              `json:"job_id"`
	Code     string              `json:"code"`
	State    string              `json:"state,omitempty"`
	Err      string              `json:"err,omitempty"`
	Debug    *DebugResult        `json:"debug,omitempty"`
	SimData  *SimData            `json:"sim_data,omitempty"`
	Progress *SimulationProgress `json:"progress,omitempty"`
}
