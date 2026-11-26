#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin gmsh "gmsh-${GMSH_VERSION}-source.tgz"
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DENABLE_BUILD_DYNAMIC=ON -DENABLE_BUILD_SHARED=ON -DENABLE_OCC=ON -DENABLE_OCC_CAF=OFF -DENABLE_OPENMP=ON \
  -DENABLE_FLTK=OFF -DENABLE_PETSC=OFF -DENABLE_SLEPC=OFF -DENABLE_MPI=OFF -DENABLE_CAIRO=OFF -DENABLE_MED=OFF -DENABLE_CGNS=OFF \
  -DENABLE_OSMESA=OFF -DENABLE_OPENGL=OFF -DENABLE_GRAPHICS=OFF -DENABLE_POPPLER=OFF -DCMAKE_PREFIX_PATH="$KFEM_SDK"
cmake --build b; cmake --install b
SP=$(pycheck "import sysconfig; print(sysconfig.get_paths()['purelib'])")
cp "$KFEM_SDK"/lib/gmsh.py "$SP/" 2>/dev/null || cp "$KFEM_SDK"/lib64/gmsh.py "$SP/"
pycheck "import gmsh; gmsh.initialize(); print('gmsh', gmsh.__version__, 'OCC' in gmsh.option.getString('General.BuildOptions')); gmsh.finalize()"; finish
