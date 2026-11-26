#!/usr/bin/env bash
# PETSc variante CPU (+MUMPS, hypre, ScaLAPACK, METIS; PT-Scotch do SDK) com OpenMP (ADR 0012) e petsc4py.
# Variantes GPU (cuda/hip/opencl) ficam para a Etapa 11, com o mesmo script e KFEM_PETSC_VARIANT.
. "$(dirname "$0")/_common.sh"; begin "petsc-$KFEM_PETSC_VARIANT" "petsc-${PETSC_VERSION}.tar.gz"
PREFIX="$PETSC_DIR"
unset CC CXX FC CFLAGS CXXFLAGS FFLAGS FCFLAGS LDFLAGS PETSC_DIR PETSC_ARCH
EXTRA=()
case "$KFEM_PETSC_VARIANT" in
  cpu) EXTRA+=(--with-cuda=0 --with-hip=0 --with-sycl=0 --with-kokkos=0) ;;
  opencl) EXTRA+=(--download-viennacl --with-opencl) ;;
  # arquitetura da placa em KFEM_CUDA_ARCH (ex.: 86 = sm_86); padrão 60 (Pascal, mínimo do KFem)
  cuda) EXTRA+=(--with-cuda --with-cuda-arch="${KFEM_CUDA_ARCH:-60}") ;;
  # ROCm do sistema (pacotes do Ubuntu em /usr); arquiteturas em KFEM_HIP_ARCH (ex.: gfx803 = RX 580)
  # Ubuntu põe as bibliotecas em lib/x86_64-linux-gnu, onde o --with-hip-dir do PETSc não procura
  # hipcc é script Perl: avisos de locale no stderr fazem o configure do PETSc recusar os testes
  hip) export LC_ALL=C.UTF-8 LANG=C.UTF-8; R="${KFEM_ROCM_DIR:-/usr}"; RL="$R/lib/x86_64-linux-gnu"; [[ -e "$RL/libamdhip64.so" ]] || RL="$R/lib"
       EXTRA+=(--with-hip --with-hipc="$R/bin/hipcc" --with-hip-arch="${KFEM_HIP_ARCH:-gfx803}"
               --with-hip-include="$R/include"
               --with-hip-lib="[-L$RL,-lhipsparse,-lhipblas,-lhipsolver,-lrocsparse,-lrocsolver,-lrocblas,-lrocrand,-lamdhip64,-lhsa-runtime64]") ;;
esac
if [[ "$KFEM_PETSC_VARIANT" == hip && ! -e "${KFEM_ROCM_DIR:-/usr}/include/rocm-core/rocm_version.h" ]]; then
  # ROCm dos pacotes do Ubuntu/Debian não tem rocm-core: a versão vem de hip/hip_version.h
  sed -i "s|'ROCM_VERSION_MAJOR.ROCM_VERSION_MINOR.ROCM_VERSION_PATCH'|'HIP_VERSION_MAJOR.HIP_VERSION_MINOR.HIP_VERSION_PATCH'|; s|\['rocm-core/rocm_version.h', 'rocm_version.h'\]|['hip/hip_version.h']|" config/BuildSystem/config/packages/HIP.py
  grep -q "HIP_VERSION_MAJOR.HIP_VERSION_MINOR" config/BuildSystem/config/packages/HIP.py || { echo "!! patch de versão do HIP não aplicado"; exit 1; }
fi
"$KFEM_SDK/bin/python3" ./configure --prefix="$PREFIX" --PETSC_ARCH=arch-kfem \
  --with-mpi-dir="$KFEM_SDK" --with-blaslapack-lib="-L$KFEM_SDK/lib -lopenblas" --with-openmp \
  --with-hdf5-dir="$KFEM_SDK" --with-ptscotch-dir="$KFEM_SDK" \
  --download-mumps --download-scalapack --download-hypre --download-metis \
  --with-debugging=0 --with-shared-libraries=1 --with-64-bit-indices=0 --with-scalar-type=real \
  COPTFLAGS="-O2" CXXOPTFLAGS="-O2" FOPTFLAGS="-O2" \
  --with-python-exec="$KFEM_SDK/bin/python3" --with-petsc4py=1 --with-x=0 "${EXTRA[@]}"
make PETSC_DIR="$PWD" PETSC_ARCH=arch-kfem MAKE_NP="$JOBS" all
make PETSC_DIR="$PWD" PETSC_ARCH=arch-kfem install
export PETSC_DIR="$PREFIX"
# petsc4py da variante CPU visível no Python do SDK durante o desenvolvimento (no AppImage o AppRun escolhe a variante)
SP=$(pycheck "import sysconfig; print(sysconfig.get_paths()['platlib'])")
[[ "$KFEM_PETSC_VARIANT" != cpu ]] || echo "$PETSC_DIR/lib" > "$SP/kfem-petsc.pth"
pycheck "import petsc4py; petsc4py.init(); from petsc4py import PETSc; print('petsc4py', PETSc.Sys.getVersion())"
finish
