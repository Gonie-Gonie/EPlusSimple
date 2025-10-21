
from .server import (
    app,
    run_simulation_comparison,
)

if __name__ == "__main__":

    app.add_url_rule("/", "run", run_simulation_comparison, methods=["GET", "POST"])
    app.run(debug=True, host="0.0.0.0", port=5000)