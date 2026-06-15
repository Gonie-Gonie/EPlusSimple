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

type SimulateResponse struct {
	JobID   string       `json:"job_id"`
	Code    string       `json:"code"`
	Err     string       `json:"err,omitempty"`
	Debug   *DebugResult `json:"debug,omitempty"`
	SimData *SimData     `json:"sim_data,omitempty"`
}
