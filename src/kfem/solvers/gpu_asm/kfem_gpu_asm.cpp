// KFem — biblioteca mínima para montagem de elementos finitos em GPU via HIP (Etapa 11).
//
// Genérica de propósito: compila um código-fonte HIP em tempo de execução (hiprtc), aloca e
// copia memória da GPU e lança kernels com um bloco de argumentos já empacotado pelo Python.
// Toda a lógica de elementos finitos (núcleos do FFCx, posições na matriz CSR) fica no
// Python (kfem.solvers.gpu_assembly). API em C para uso com ctypes.
//
// SPDX-License-Identifier: GPL-3.0-or-later

#include <hip/hip_runtime.h>
#include <hip/hiprtc.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

struct Handle {
  hipModule_t module = nullptr;
  std::vector<hipFunction_t> kernels;
};

void put_err(char* err, int errlen, const std::string& msg) {
  if (err && errlen > 0) {
    std::strncpy(err, msg.c_str(), static_cast<size_t>(errlen - 1));
    err[errlen - 1] = '\0';
  }
}

int check(hipError_t e, char* err, int errlen, const char* what) {
  if (e == hipSuccess) return 0;
  put_err(err, errlen, std::string(what) + ": " + hipGetErrorString(e));
  return static_cast<int>(e);
}

}  // namespace

extern "C" {

// Nome da arquitetura da GPU 0 (ex.: gfx803). Retorna 0 se houver GPU.
int kga_device(char* arch, int len, char* name, int namelen) {
  int n = 0;
  if (hipGetDeviceCount(&n) != hipSuccess || n == 0) return 1;
  hipDeviceProp_t p;
  if (hipGetDeviceProperties(&p, 0) != hipSuccess) return 2;
  put_err(arch, len, p.gcnArchName);
  put_err(name, namelen, p.name);
  return 0;
}

// Compila `src` e devolve um identificador com os kernels `names` (na ordem dada).
void* kga_compile(const char* src, const char** names, int nnames, const char* extra_opts, char* err, int errlen) {
  hipDeviceProp_t p;
  if (hipGetDeviceProperties(&p, 0) != hipSuccess) {
    put_err(err, errlen, "nenhuma GPU HIP");
    return nullptr;
  }
  hiprtcProgram prog;
  if (hiprtcCreateProgram(&prog, src, "kfem_asm.hip", 0, nullptr, nullptr) != HIPRTC_SUCCESS) {
    put_err(err, errlen, "hiprtcCreateProgram falhou");
    return nullptr;
  }
  std::string arch = std::string("--gpu-architecture=") + p.gcnArchName;
  std::vector<std::string> opts = {arch, "-O3"};
  if (extra_opts && *extra_opts) opts.emplace_back(extra_opts);
  std::vector<const char*> copts;
  for (auto& o : opts) copts.push_back(o.c_str());
  hiprtcResult r = hiprtcCompileProgram(prog, static_cast<int>(copts.size()), copts.data());
  if (r != HIPRTC_SUCCESS) {
    size_t ls = 0;
    hiprtcGetProgramLogSize(prog, &ls);
    std::string log(ls, '\0');
    if (ls) hiprtcGetProgramLog(prog, &log[0]);
    put_err(err, errlen, "compilação hiprtc falhou: " + log);
    hiprtcDestroyProgram(&prog);
    return nullptr;
  }
  size_t cs = 0;
  hiprtcGetCodeSize(prog, &cs);
  std::vector<char> code(cs);
  hiprtcGetCode(prog, code.data());
  hiprtcDestroyProgram(&prog);
  auto* h = new Handle();
  if (check(hipModuleLoadData(&h->module, code.data()), err, errlen, "hipModuleLoadData")) {
    delete h;
    return nullptr;
  }
  for (int i = 0; i < nnames; ++i) {
    hipFunction_t f;
    if (check(hipModuleGetFunction(&f, h->module, names[i]), err, errlen, names[i])) {
      hipModuleUnload(h->module);
      delete h;
      return nullptr;
    }
    h->kernels.push_back(f);
  }
  return h;
}

void kga_destroy(void* hv) {
  auto* h = static_cast<Handle*>(hv);
  if (!h) return;
  if (h->module) hipModuleUnload(h->module);
  delete h;
}

// Memória da GPU. Endereços trafegam como uint64 no Python.
uint64_t kga_alloc(size_t bytes) {
  void* d = nullptr;
  if (hipMalloc(&d, bytes ? bytes : 8) != hipSuccess) return 0;
  return reinterpret_cast<uint64_t>(d);
}

void kga_free(uint64_t d) {
  if (d) hipFree(reinterpret_cast<void*>(d));
}

int kga_h2d(uint64_t d, const void* host, size_t bytes) {
  return static_cast<int>(hipMemcpy(reinterpret_cast<void*>(d), host, bytes, hipMemcpyHostToDevice));
}

int kga_d2h(void* host, uint64_t d, size_t bytes) {
  return static_cast<int>(hipMemcpy(host, reinterpret_cast<void*>(d), bytes, hipMemcpyDeviceToHost));
}

int kga_zero(uint64_t d, size_t bytes) {
  return static_cast<int>(hipMemset(reinterpret_cast<void*>(d), 0, bytes));
}

// Lança o kernel `k` com `n` itens (1 thread por item) e o bloco de argumentos `args`.
int kga_launch(void* hv, int k, int n, int block, void* args, size_t argsize) {
  auto* h = static_cast<Handle*>(hv);
  if (!h || k < 0 || k >= static_cast<int>(h->kernels.size())) return -1;
  if (n <= 0) return 0;
  unsigned grid = static_cast<unsigned>((n + block - 1) / block);
  void* cfg[] = {HIP_LAUNCH_PARAM_BUFFER_POINTER, args, HIP_LAUNCH_PARAM_BUFFER_SIZE, &argsize, HIP_LAUNCH_PARAM_END};
  return static_cast<int>(hipModuleLaunchKernel(h->kernels[k], grid, 1, 1, static_cast<unsigned>(block), 1, 1, 0,
                                                nullptr, nullptr, cfg));
}

int kga_sync() { return static_cast<int>(hipDeviceSynchronize()); }

const char* kga_error_string(int e) { return hipGetErrorString(static_cast<hipError_t>(e)); }

}  // extern "C"
