package main

import (
	"net/http"
	"strings"
	"time"
)

func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	select {
	case <-a.ready:
		// continue
	case <-time.After(30 * time.Second):
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{
			"err": "EPlusSimple launcher is still starting. Please close and reopen the launcher if this continues.",
		})
		return
	}

	if a.startupErr != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"err": "EPlusSimple launcher failed to start: " + a.startupErr.Error(),
		})
		return
	}

	switch {
	case r.Method == http.MethodGet && (r.URL.Path == "/" || r.URL.Path == "/index.html"):
		a.serveIndex(w, r)
		return

	case r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/assets/"):
		a.frontend.ServeHTTP(w, r)
		return

	case r.Method == http.MethodGet && r.URL.Path == "/api/health":
		writeJSON(w, http.StatusOK, map[string]any{
			"ok": true,
		})
		return

	case r.Method == http.MethodPost && r.URL.Path == "/api/simulate":
		a.handleSimulate(w, r)
		return

	default:
		http.NotFound(w, r)
		return
	}
}

func (a *App) serveIndex(w http.ResponseWriter, r *http.Request) {
	indexHTML, err := readEmbeddedIndex()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"err": "failed to read embedded index.html: " + err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write(indexHTML)
}
