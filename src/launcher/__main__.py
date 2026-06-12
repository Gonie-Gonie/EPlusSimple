
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os
from pathlib import Path

# third-party modules
from flask import Flask

# local modules
# DO NOT IMPORT RELATIVELY
from .core import getpost

# ---------------------------------------------------------------------------- #
#                       APP DEFINITION AND INITIALIZATION                      #
# ---------------------------------------------------------------------------- #

def initialize_app(
    *,
    upload_dirpath   = None,
    static_dirname   = None,
    ) -> Flask:
    
    # define and create upload direcotry
    if upload_dirpath is None:
        upload_dirpath = Path(__file__).parent / "uploads"
    if not os.path.exists(upload_dirpath):
        os.mkdir(upload_dirpath)
    
    # define static/template directory
    if static_dirname is None:
        static_dirname = "static"
    
    package_dirpath = Path(__file__).resolve().parent
    static_dirpath = package_dirpath / static_dirname
    template_dirpath = package_dirpath / "templates"
    
    # create a flask app 
    app = Flask(__name__,
        static_folder  =static_dirpath  ,
        template_folder=template_dirpath,
    )
    
    # and set default options
    app.config["UPLOAD_FOLDER"] = upload_dirpath
    app.config["JSON_AS_ASCII"] = False
    
    return app

def create_app() -> Flask:
    app = initialize_app()
    app.add_url_rule("/", "main", getpost, methods=["GET", "POST"])
    return app


def main() -> None:
    host = os.environ.get("EPLUSSIMPLE_LAUNCHER_HOST", "127.0.0.1")
    port = int(os.environ.get("EPLUSSIMPLE_LAUNCHER_PORT", "5000"))

    debug_text = os.environ.get("EPLUSSIMPLE_LAUNCHER_DEBUG", "0").strip().lower()
    debug = debug_text in {"1", "true", "yes", "on"}

    app = create_app()

    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()