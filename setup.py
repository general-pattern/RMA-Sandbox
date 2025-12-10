from cx_Freeze import setup, Executable

build_options = {
    "packages": ["flask", "werkzeug", "sqlite3"],
    "include_files": [
        "rma.db",
        "templates",
        "static"
    ]
}

setup(
    name="RMA_Server",
    version="1.0",
    description="Internal RMA Web App Server",
    options={"build_exe": build_options},
    executables=[Executable("app.py", base=None)],
)
