#!/bin/bash
set -euo pipefail
export LANSUS_BUILD_TARGET=centos7
exec /src/build/linux/common/build.sh
