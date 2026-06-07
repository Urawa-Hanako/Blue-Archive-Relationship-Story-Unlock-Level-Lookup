import os
import subprocess
import sys
from pathlib import Path


APP_NAME = "\u597d\u611f\u5267\u60c5\u89e3\u9501\u7b49\u7ea7\u67e5\u8be2"
ENTRY_SCRIPT = Path("query_favor_levels.py")
DATA_FILE = Path("character_favor_levels.json")
BUILD_VENV = Path(".venv-build")
DIST_DIR = Path("dist")
PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PYPI_HOST = "pypi.tuna.tsinghua.edu.cn"


def ensure_file_exists(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")


def venv_python():
    return BUILD_VENV / "Scripts" / "python.exe"


def ensure_build_venv():
    python = venv_python()
    if python.exists():
        return python

    subprocess.check_call([sys.executable, "-m", "venv", str(BUILD_VENV)])
    return python


def ensure_pyinstaller(python):
    check = subprocess.run(
        [str(python), "-c", "import PyInstaller"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        return

    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "pyinstaller",
            "-i",
            PYPI_MIRROR,
            "--trusted-host",
            PYPI_HOST,
            "--disable-pip-version-check",
        ]
    )


def build():
    ensure_file_exists(ENTRY_SCRIPT)
    ensure_file_exists(DATA_FILE)

    python = ensure_build_venv()
    ensure_pyinstaller(python)

    add_data = f"{DATA_FILE.resolve()}{os.pathsep}."
    command = [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--add-data",
        add_data,
        str(ENTRY_SCRIPT),
    ]
    subprocess.check_call(command)

    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Build finished, but exe was not found: {exe_path}")

    print(f"Built: {exe_path.resolve()}")


if __name__ == "__main__":
    build()
