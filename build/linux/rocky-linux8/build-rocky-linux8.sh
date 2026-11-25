#!/bin/bash
set -euo pipefail
export LANSUS_BUILD_TARGET=rocky8
exec /src/build/linux/common/build.sh
