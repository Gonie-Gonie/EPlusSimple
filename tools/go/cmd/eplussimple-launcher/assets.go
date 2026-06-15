package main

import (
	"embed"
	"io/fs"
	"net/http"
)

//go:embed frontend
var embeddedFrontend embed.FS

func newFrontendHandler() (http.Handler, error) {
	frontendFS, err := fs.Sub(embeddedFrontend, "frontend")
	if err != nil {
		return nil, err
	}

	return http.FileServer(http.FS(frontendFS)), nil
}

func readEmbeddedIndex() ([]byte, error) {
	return embeddedFrontend.ReadFile("frontend/index.html")
}
