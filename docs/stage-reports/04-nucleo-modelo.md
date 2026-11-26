# Etapa 4 — Núcleo do modelo · relatório

**Data:** 2026-11-18 · **Status:** concluída.

## Feito
- `kfem.model.expressions`: expressões com unidades, interpretadas por parser próprio
  (sem `eval`). Aceitam unidade pós-fixa `[mm]`, funções, potência e comparações. As
  unidades usam o pint, e as constantes físicas são do CODATA.
- `kfem.model.parameters`: grupos de parâmetros, ordem topológica, detecção de ciclos e de
  símbolos desconhecidos, sobrescritas (para varreduras) e valores em SI.
- `kfem.model.tree`: árvore genérica (`Node`, `Selection`, `Component`, `Model`) com caminhos
  do tipo `comp1/physics/tds/in1`.
- `kfem.model.catalog`: tipos de nó do KFem, com rótulos em pt-BR, propriedades e padrões.
  É de onde saem os painéis da interface, e o conversor e o solver usam os mesmos tipos.
- `kfem.io.kfem_format`: o `.kfem` é um ZIP com `model.json` versionado mais anexos (malha e
  resultados), e a gravação é atômica.

## Verificação
- `pytest tests/model`: unidades, precedência, segurança contra `eval`, valores do caso CDI
  (C = 28,41 F; C_v = 7,10·10⁷ F/m³; v0 = 4,375·10⁻⁴ m/s), ciclos, ida e volta do
  `.kfem` com anexos, e rejeição de arquivo de outro formato.

## Commit sugerido
`Etapa 4: expressões com unidades, parâmetros, árvore do modelo e formato .kfem`
