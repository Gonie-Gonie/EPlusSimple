# EPlusSimple

**EPlusSimple** is an open-source building energy simulation engine. It simplifies the complex EnergyPlus workflow by using a spreadsheet-centric data structure and graph-based spatial relationship visualization.

## Installation & Setup

This project is designed to be **portable**. You do not need to install Python or manage libraries manually.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Gonie-Gonie/EPlusSimple.git](https://github.com/Gonie-Gonie/EPlusSimple.git)
    cd EPlusSimple
    ```
2.  **Initialize Environment:**
    Run `setup.bat`. This will create a local portable Python environment (`venv`) and install all required dependencies from `requirements.txt` automatically.


## How to Run

There are two primary ways to interact with the engine:

### 1. CLI Mode (Simulation Engine)
Use `runEngine.bat` for direct simulation or format conversion via the command line.

* **Run Simulation:**
    ```bash
    runEngine.bat run -i your_model.grm -o your_output_destinaton.grr
    ```
* **Convert Formats (e.g., Excel to IDF):**
    ```bash
    runEngine.bat convert your_model.xlsx -s excel -d idf
    ```

### 2. Web GUI Mode (Excel Launcher)
Use `runExcelLauncher.bat` to launch a user-friendly web interface.

1.  Double-click `runExcelLauncher.bat`.
2.  A local Flask server will start, and the launcher will open a local web interface.
3.  Upload your "Before" and "After" Excel files to visualize energy performance differences and debug reports.
