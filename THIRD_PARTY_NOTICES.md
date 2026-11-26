# Avisos de terceiros

Componentes compilados e embutidos no AppImage. Os textos completos das licenças vão em
`usr/share/licenses/` dentro do AppImage (Etapa 12). Dependências Python puras usadas em
tempo de execução constam em `build/python-runtime.lock` e `build/python-viz.lock`, com as
licenças conferidas na Etapa 12. Ferramentas usadas só no build (bison, flex, CMake, Ninja,
ccache, libclang) não entram no pacote.

| Componente | Versão | Licença | Origem |
|---|---|---|---|
| Python | 3.14.10 | PSF-2.0 | python.org |
| OpenBLAS | 0.3.34 | BSD-3-Clause | github.com/OpenMathLib/OpenBLAS |
| MPICH | 5.0.2 | MPICH (BSD-like) | mpich.org |
| HDF5 | 2.2.0 | BSD-3-Clause (HDF5) | github.com/HDFGroup/hdf5 |
| PT-Scotch | 7.0.18 | CeCILL-C | gitlab.inria.fr/scotch |
| Boost (cabeçalhos) | 1.92.0 | BSL-1.0 | boost.org |
| PETSc + petsc4py | 3.26.1 | BSD-2-Clause | petsc.org |
| MUMPS (via PETSc) | (versão fixada pelo PETSc) | CeCILL-C | mumps-solver.org |
| hypre (via PETSc) | (versão fixada pelo PETSc) | MIT OR Apache-2.0 | github.com/hypre-space/hypre |
| ScaLAPACK (via PETSc) | (versão fixada pelo PETSc) | BSD-3-Clause | netlib.org/scalapack |
| METIS (via PETSc) | (versão fixada pelo PETSc) | Apache-2.0 | github.com/KarypisLab/METIS |
| NumPy | 2.5.5 | BSD-3-Clause | numpy.org |
| cffi | 2.1.1 | MIT | cffi.readthedocs.io |
| mpi4py | 4.1.2 | BSD-3-Clause | mpi4py.github.io |
| h5py | 3.16.0 | BSD-3-Clause | h5py.org |
| spdlog | 1.17.0 | MIT | github.com/gabime/spdlog |
| pugixml | 1.16 | MIT | pugixml.org |
| Basix | 0.11.0 | MIT | github.com/FEniCS/basix |
| UFL | 2026.1.0 | LGPL-3.0-or-later | github.com/FEniCS/ufl |
| FFCx | 0.11.0 | LGPL-3.0-or-later | github.com/FEniCS/ffcx |
| DOLFINx | 0.11.0 | LGPL-3.0-or-later | github.com/FEniCS/dolfinx |
| ADIOS2 | 2.12.1 | Apache-2.0 | github.com/ornladios/ADIOS2 |
| Open CASCADE Technology | 7.9.3 | LGPL-2.1 com exceção | github.com/Open-Cascade-SAS/OCCT |
| Gmsh | 4.15.2 | GPL-2.0-or-later | gmsh.info |
| meshio | 5.3.5 | MIT | github.com/nschloe/meshio |
| Pint | 0.26.2 | BSD-3-Clause | github.com/hgrecco/pint |
| Qt 6 (qtbase, qtsvg, qttools) | 6.12.0 | LGPL-3.0 | qt.io |
| PySide6 / Shiboken6 | 6.12.0 | LGPL-3.0 | qt.io/qt-for-python |
| VTK | 9.7.2 | BSD-3-Clause | vtk.org |
| Matplotlib | 3.11.2 | Matplotlib License (PSF-like) | matplotlib.org |
| PyVista | 0.49.1 | MIT | pyvista.org |
| pyvistaqt | 0.13.2 | MIT | github.com/pyvista/pyvistaqt |
| ViennaCL (via PETSc, variante OpenCL) | 1.7.1 | MIT | viennacl.sourceforge.net |
| AppImage type2-runtime | continuous (hash em `build/sha256.lock`) | MIT | github.com/AppImage/type2-runtime |

Bibliotecas do **sistema** usadas em tempo de execução e **não** empacotadas: driver de
vídeo (libGL/EGL/Vulkan/DRM), ICDs OpenCL, libcuda/ROCm, X11/xcb, fontconfig e glibc.
A variante PETSc HIP e a biblioteca de montagem em GPU do KFem (`libkfem_gpu_asm.so`, código
próprio, GPL-3.0-or-later) ligam ao runtime ROCm do sistema (libamdhip64, hipSPARSE,
rocSPARSE, rocBLAS, rocSOLVER, hiprtc, comgr; licenças MIT/Apache/NCSA da AMD); sem ele o KFem
calcula na CPU. O script `kfem-gpu-setup` instala esse runtime pelos pacotes da distribuição.
Em tempo de execução a DOLFINx usa o compilador C do sistema (gcc) para os núcleos de cada
modelo; ele não é empacotado.

## Logotipo e ícone do KFem

`packaging/icons/kfem-logo.png`, `packaging/icons/kfem.png` e `src/kfem/gui/assets/*.png`:
logotipo fornecido pelo autor do projeto (2026-11-18). O ícone é um recorte do "K" desse
logotipo. Não vem de terceiros.
