package main

import (
	"path/filepath"
	"strings"
)

const (
	inputKindExcel  = "excel"
	inputKindGRJSON = "grjson"
)

func inputKindForFilename(name string) string {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".xlsx", ".xlsm", ".xls":
		return inputKindExcel
	case ".grm":
		return inputKindGRJSON
	default:
		return ""
	}
}

func isExcelInputFile(name string) bool {
	return inputKindForFilename(name) == inputKindExcel
}

func isSupportedInputFile(name string) bool {
	return inputKindForFilename(name) != ""
}
