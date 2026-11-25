#!/bin/bash
set -euo pipefail

cd /src
export PATH="/usr/local/bin:${PATH}"
root=/tmp/mipi-build
mkdir -p "${root}/cache" "${root}/pyinstaller" "${root}/python"
export UV_PROJECT_ENVIRONMENT="${root}/venv"
export UV_CACHE_DIR="${root}/cache"
export UV_PYTHON_INSTALL_DIR="${root}/python"
export UV_LINK_MODE=copy

version="$(tr -d '[:space:]' < .python-version)"
uv python install "${version}"
interp="$(uv python find "${version}")"
"${interp}" -c 'import sys; print(sys.version); print(sys.executable)'

uv sync --frozen --group dev --python "${interp}"
uv run --frozen --no-sync --python "${interp}" \
    python -c 'import tkinter, pandas, xlrd, openpyxl, numpy; print(numpy.__version__)'

target="${LANSUS_BUILD_TARGET:?需要 LANSUS_BUILD_TARGET}"
case "${target}" in
    centos7|rocky8) ;;
    *)
        echo "未知构建目标: ${target}" >&2
        exit 1
        ;;
esac

LANSUS_BUILD_TARGET="${target}" uv run --frozen --no-sync --python "${interp}" \
    pyinstaller --clean \
    --workpath "${root}/pyinstaller" \
    --distpath /out \
    build/linux/common/mipi_gui.spec

test -x /out/mipi_gui/mipi_gui
