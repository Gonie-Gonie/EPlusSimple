
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import importlib

# third-party modules


# local modules
# DO NOT IMPORT RELATIVELY
from config import TEMPLATE_NAME, COREMODULE_NAME

source = importlib.import_module(COREMODULE_NAME)





if __name__ == "__main__":

    source.app.add_url_rule("/", TEMPLATE_NAME, source.run_simulation_comparison, methods=["GET", "POST"])
    source.app.run(debug=True, host="0.0.0.0", port=5000)