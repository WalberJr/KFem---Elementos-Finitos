#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin numpy "numpy-${NUMPY_VERSION}.tar.gz"
pyinst . -Csetup-args=-Dblas=openblas -Csetup-args=-Dlapack=openblas
pycheck "import numpy; numpy.show_config()"; finish
