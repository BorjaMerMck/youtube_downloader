import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_NAME = "YouTubeDownloader"
ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
ZIP_NAME = ROOT_DIR / f"{PROJECT_NAME}.zip"


def run(command):
    print(f"\nEjecutando: {command}")
    subprocess.run(command, check=True, cwd=ROOT_DIR)


def clean():
    print("\nLimpiando compilaciones anteriores...")

    for folder in [DIST_DIR, BUILD_DIR]:
        if folder.exists():
            shutil.rmtree(folder)

    if ZIP_NAME.exists():
        ZIP_NAME.unlink()


def install_dependencies():
    print("\nInstalando dependencias...")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_exe():
    print("\nCompilando ejecutable...")

    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        str(ROOT_DIR / "YouTubeDownloader.spec"),
    ])


def create_zip():
    print("\nCreando archivo ZIP...")

    app_folder = DIST_DIR / PROJECT_NAME

    if not app_folder.exists():
        raise FileNotFoundError(f"No existe la carpeta: {app_folder}")

    shutil.make_archive(
        base_name=str(ROOT_DIR / PROJECT_NAME),
        format="zip",
        root_dir=app_folder
    )


def main():
    try:
        for filename in ("ico.png", "ico.ico", "YouTubeDownloader.spec"):
            if not (ROOT_DIR / filename).is_file():
                raise FileNotFoundError(f"Falta {filename} en la raíz del proyecto")
        clean()
        install_dependencies()
        build_exe()
        create_zip()

        print("\nCOMPILACION COMPLETADA")
        print(f"Archivo generado: {ZIP_NAME}")

    except Exception as error:
        print("\nError durante la compilacion:")
        print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()