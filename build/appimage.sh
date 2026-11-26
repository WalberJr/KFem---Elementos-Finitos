#!/usr/bin/env bash
# Monta o AppDir a partir do SDK e gera o AppImage (Etapa 12).
#
#   build/appimage.sh [SAIDA.AppImage]
#
# Ferramenta: appimagetool, se estiver em $KFEM_SDK/tools/bin; senão, mksquashfs + o runtime
# oficial do AppImage (type2-runtime, arquivo runtime-x86_64 em $KFEM_DL, conferido pelo
# SHA-256 em build/sha256.lock), o mesmo que o appimagetool faz.
set -euo pipefail
. "$(dirname "$0")/env.sh"
APPDIR="$KFEM_BUILD/AppDir"; OUT="${1:-$KFEM_BUILD/KFem-x86_64.AppImage}"
PYV=$("$KFEM_SDK/bin/python3" -c 'import sys; print(f"python{sys.version_info[0]}.{sys.version_info[1]}")')
rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/share/kfem"

# SDK sem ferramentas de build, estáticas, documentação e cabeçalhos — exceto os do Python,
# que o JIT da DOLFINx (cffi) usa para compilar os núcleos de cada modelo
rsync -a \
  --include "/include/" --include "/include/$PYV/***" --exclude "/include/*" \
  --exclude 'include/' --exclude '*.a' --exclude '/tools/' --exclude 'share/doc' --exclude 'share/man' \
  --exclude '.stamps' --exclude '__pycache__' --exclude "lib/$PYV/test/" --exclude 'lib/pkgconfig/' \
  --exclude 'lib/cmake/' --exclude 'share/aclocal' --exclude 'share/info' \
  "$KFEM_SDK/" "$APPDIR/usr/"
# o .pth da variante CPU tem caminho absoluto do SDK; no AppImage quem escolhe é o AppRun
find "$APPDIR/usr/lib/$PYV/site-packages" -maxdepth 1 -name 'kfem-petsc.pth' -delete
# código do KFem (sem caches) e scripts
rsync -a --exclude '__pycache__' "$KFEM_ROOT/src/" "$APPDIR/usr/share/kfem/src/"
install -m 755 "$KFEM_ROOT/packaging/kfem-gpu-setup.sh" "$APPDIR/usr/bin/kfem-gpu-setup"
install -m 755 "$KFEM_ROOT/packaging/AppRun" "$APPDIR/AppRun"
cp "$KFEM_ROOT/packaging/kfem.desktop" "$APPDIR/"
cp "$KFEM_ROOT/packaging/icons/kfem.png" "$APPDIR/kfem.png"
ln -sf kfem.png "$APPDIR/.DirIcon"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps" "$APPDIR/usr/share/applications"
cp "$KFEM_ROOT/packaging/icons/kfem.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/kfem.png"
for sz in 256 128 64 48; do  # tamanhos padrão do tema de ícones (menu, gerenciador de arquivos)
  mkdir -p "$APPDIR/usr/share/icons/hicolor/${sz}x${sz}/apps"
  "$KFEM_SDK/bin/python3" -c "import sys; from PIL import Image; Image.open(sys.argv[1]).resize((int(sys.argv[3]),)*2, Image.LANCZOS).save(sys.argv[2])" \
    "$KFEM_ROOT/packaging/icons/kfem.png" "$APPDIR/usr/share/icons/hicolor/${sz}x${sz}/apps/kfem.png" "$sz" 2>/dev/null \
    || cp "$KFEM_ROOT/packaging/icons/kfem.png" "$APPDIR/usr/share/icons/hicolor/${sz}x${sz}/apps/kfem.png"
done
cp "$KFEM_ROOT/packaging/kfem.desktop" "$APPDIR/usr/share/applications/kfem.desktop"
mkdir -p "$APPDIR/usr/share/metainfo" "$APPDIR/usr/share/licenses/kfem"
cp "$KFEM_ROOT/packaging/kfem.appdata.xml" "$APPDIR/usr/share/metainfo/org.kfem.KFem.appdata.xml"
cp "$KFEM_ROOT/LICENSE" "$KFEM_ROOT/THIRD_PARTY_NOTICES.md" "$APPDIR/usr/share/licenses/kfem/"
# manual e tutorial (abertos pelo menu Ajuda)
mkdir -p "$APPDIR/usr/share/doc/kfem"
cp "$KFEM_ROOT/docs/usuario/KFem-Manual.pdf" "$KFEM_ROOT/docs/usuario/KFem-Tutorial.pdf" "$APPDIR/usr/share/doc/kfem/"
# nunca empacotar drivers/bibliotecas de vídeo e de GPU do sistema (ADR 0005/0013)
find "$APPDIR/usr" \( -name 'libGL*.so*' -o -name 'libvulkan*.so*' -o -name 'libdrm*.so*' -o -name 'libcuda*.so*' \
  -o -name 'libEGL*.so*' -o -name 'libOpenCL*.so*' -o -name 'libamdhip64*.so*' -o -name 'libhsa-runtime*.so*' \
  -o -name 'librocsparse*.so*' -o -name 'librocblas*.so*' \) -delete
find "$APPDIR/usr" -name '*.so*' -type f -exec strip --strip-unneeded {} + 2>/dev/null || true
echo "AppDir: $(du -sh "$APPDIR" | cut -f1)"

if [[ -x "$KFEM_SDK/tools/bin/appimagetool" ]]; then
  ARCH=x86_64 "$KFEM_SDK/tools/bin/appimagetool" --appimage-extract-and-run "$APPDIR" "$OUT"
else
  RT="$KFEM_DL/runtime-x86_64"
  [[ -s "$RT" ]] || { echo "!! runtime do AppImage ausente: rode build/fetch.sh appimage-runtime"; exit 1; }
  (cd "$KFEM_DL" && grep "  runtime-x86_64\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -) \
    || { echo "!! SHA-256 do runtime não confere"; exit 1; }
  SQ="$KFEM_BUILD/kfem.squashfs"; rm -f "$SQ"
  mksquashfs "$APPDIR" "$SQ" -root-owned -noappend -comp zstd -Xcompression-level 19 -b 1M -quiet
  # grava ao lado e troca no fim: funciona mesmo com o AppImage antigo aberto e nunca deixa
  # um arquivo pela metade no lugar do bom
  cat "$RT" "$SQ" > "$OUT.tmp"; chmod +x "$OUT.tmp"; mv -f "$OUT.tmp" "$OUT"; rm -f "$SQ"
fi
ls -lh "$OUT"
sha256sum "$OUT" | tee "$OUT.sha256"
