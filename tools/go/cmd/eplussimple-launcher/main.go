package main

import (
	"log"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

const (
	pythonFolderName = "PythonV3-12-7"
	logFileName      = "launcher.log"

	createNoWindow = 0x08000000
)

func main() {
	app := NewApp()

	err := wails.Run(&options.App{
		Title:     "EPlusSimple Launcher",
		Width:     1200,
		Height:    820,
		MinWidth:  900,
		MinHeight: 650,

		AssetServer: &assetserver.Options{
			Assets:  nil,
			Handler: app,
		},

		OnStartup:  app.startup,
		OnShutdown: app.shutdown,

		EnableDefaultContextMenu: false,
	})

	if err != nil {
		log.Fatal(err)
	}
}
