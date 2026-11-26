#!/usr/bin/env bash
# DOLFINx só precisa dos cabeçalhos do Boost.
. "$(dirname "$0")/_common.sh"; begin boost "boost-${BOOST_VERSION}.tar.gz"
mkdir -p "$KFEM_SDK/include/boost"
find libs -type d -path "*/include/boost" | while read -r d; do cp -r "$d/." "$KFEM_SDK/include/boost/"; done
test -f "$KFEM_SDK/include/boost/version.hpp"
# CMake 4 não traz mais o FindBoost: gera uma configuração mínima só de cabeçalhos
cp -r "$KFEM_ROOT/build/cmake/Boost" "$KFEM_SDK/lib/cmake/Boost-${BOOST_VERSION}"
finish
