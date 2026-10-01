# MLOps, Expansão de Dados e Correção de Viés Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as três lacunas identificadas na revisão contra o framework MLOps (Kreuzberger, Kühl & Hirschl, arXiv:2205.02302): ausência de CI/CD e versionamento de modelo, extração de alegação quase nunca ativada, e viés de fonte da Camada 1 nunca medido.

**Architecture:** Um novo script (`prepara_fakerecogna.py`) reusa `ingestao.extrair_noticia` para gerar uma segunda fonte de dados de saúde em português a partir de URLs do FakeRecogna. Um novo módulo (`model_card.py`) versiona treino/métricas/hash em JSON no git, substituindo o `.joblib` solto. Uma nova rotina de avaliação cross-source mede o viés de fonte como métrica formal. Dois workflows GitHub Actions (CI rápido + gate de treino manual) automatizam o que hoje é só manual.

**Tech Stack:** Python 3.11, pandas, pyarrow (leitura de Parquet), scikit-learn, GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-10-01-mlops-e-expansao-de-dados-design.md](../specs/2026-10-01-mlops-e-expansao-de-dados-design.md)

## Global Constraints

- **Python 3.11+** — sintaxe `tipo | None` exige 3.10 no mínimo (já em uso no projeto).
- **Orçamento zero** — nenhuma dependência de API paga, nenhum servidor hospedado.
- **Testes sem rede** — nenhum teste novo pode fazer requisição HTTP real. Toda função que acessa rede é dividida em parte pura (testada) e casca de I/O (não testada em unidade). Testes que precisam tocar rede de verdade (ex.: os já existentes `test_classificador_bert.py`) usam `@pytest.mark.rede` — nenhuma tarefa deste plano adiciona um novo teste marcado assim.
- **Português no código** — nomes de funções, variáveis e mensagens em português; termos técnicos consagrados (`fit`, `predict`, `hash`, `commit`) permanecem em inglês.
- **Commits em português**, prefixo convencional (`feat:`, `test:`, `docs:`, `chore:`), um commit por tarefa concluída no mínimo.
- **Extração do FakeRecogna é manual, nunca roda em CI automatizado** (decisão do usuário) — evita repetir ~4.456 requisições HTTP a cada push.
- **O CSV gerado pela extração do FakeRecogna é commitado no git**, ao contrário do padrão atual de gitignorar `dados/processed/` — porque não é regenerável em segundos como o Fake.br (decisão do usuário).

## Review Focus

- **Parquet do FakeRecogna com schema diferente do esperado** (coluna renomeada, categoria com capitalização diferente) — o script deve falhar com mensagem clara, não silenciosamente processar 0 linhas. Teste na Tarefa 2.
- **Todas as URLs do FakeRecogna falhando na extração** (rede fora do ar, todos os links mortos) — o script deve reportar taxa de extração 0% e não gerar um CSV vazio que passa despercebido como "sucesso". Teste na Tarefa 2.
- **Model card com métricas ausentes ou `None`** (ex.: cross-source não foi calculado ainda) — `aprovar_gate` não deve lançar exceção nem aprovar por omissão; deve reprovar explicitamente. Teste na Tarefa 3.
- **Hash do artefato não bate com o registrado no card** (modelo foi retreinado localmente mas o card não foi atualizado, ou arquivo corrompido) — `app.py` deve mostrar erro visível ao usuário, nunca servir silenciosamente. Teste na Tarefa 5.
- **Dataset cross-source com uma única fonte presente** (ex.: alguém roda o treino antes de gerar o FakeRecogna) — a rotina de avaliação cross-source deve avisar e pular essa etapa, não quebrar o treino same-source que já funciona. Teste na Tarefa 4.

---

## Task 1: Fixture do FakeRecogna e teste de leitura do parquet

**Files:**
- Create: `tests/fixtures/fakerecogna_mini.parquet`
- Create: `tests/test_prepara_fakerecogna.py`
- Create: `scripts/prepara_fakerecogna.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produz: `ler_fakerecogna(caminho_parquet: Path) -> pd.DataFrame` com colunas `["Titulo", "Noticia", "Categoria", "URL", "Classe"]`
- Produz: `filtrar_categoria_saude(df: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 0: Adicionar `pyarrow` a `requirements.txt`**

`pd.read_parquet` exige o pacote `pyarrow` instalado — sem ele, tanto o teste
desta tarefa quanto o CI (que instala a partir de `requirements.txt` em um
ambiente limpo) falham com `ImportError: Unable to find a usable engine`.
Adicionar a `requirements.txt`, junto das demais dependências de dados:

```
pyarrow>=14
```

Rodar `pip install -r requirements.txt` (ou só `pip install pyarrow>=14` no
venv local) antes de prosseguir.

- [ ] **Step 1: Gerar a fixture parquet mínima**

Criar um script Python temporário (não faz parte do repositório) para gerar a fixture, e rodá-lo uma vez:

```python
import pandas as pd

df = pd.DataFrame({
    "Titulo": [
        "Vacina causa autismo segundo post viral",
        "Ministério da Saúde amplia campanha de vacinação",
        "Ator famoso é encontrado morto em casa",
        "Chá de boldo cura câncer em uma semana",
    ],
    "Noticia": ["texto lematizado irrelevante"] * 4,
    "Categoria": ["saúde", "saúde", "entretenimento", "saúde"],
    "URL": [
        "https://exemplo-fixture.invalid/saude/vacina-autismo",
        "https://exemplo-fixture.invalid/saude/campanha-vacinacao",
        "https://exemplo-fixture.invalid/entretenimento/ator-morto",
        "https://exemplo-fixture.invalid/saude/cha-boldo-cancer",
    ],
    "Classe": [0.0, 1.0, 0.0, 0.0],
})
df.to_parquet("tests/fixtures/fakerecogna_mini.parquet", index=False)
```

Rodar com `venv/bin/python3 gerar_fixture_temp.py` a partir da raiz do projeto, depois apagar o script temporário. O arquivo `tests/fixtures/fakerecogna_mini.parquet` deve existir e ter ~5-10KB.

- [ ] **Step 2: Escrever o teste falho**

Criar `tests/test_prepara_fakerecogna.py`:

```python
from pathlib import Path

from prepara_fakerecogna import filtrar_categoria_saude, ler_fakerecogna

FIXTURE = Path(__file__).parent / "fixtures" / "fakerecogna_mini.parquet"


def test_le_o_parquet_com_as_colunas_esperadas():
    df = ler_fakerecogna(FIXTURE)
    assert list(df.columns) == ["Titulo", "Noticia", "Categoria", "URL", "Classe"]
    assert len(df) == 4


def test_filtra_apenas_categoria_saude():
    df = ler_fakerecogna(FIXTURE)
    saude = filtrar_categoria_saude(df)
    assert len(saude) == 3
    assert set(saude["Categoria"]) == {"saúde"}


def test_filtra_preserva_classe_original():
    df = ler_fakerecogna(FIXTURE)
    saude = filtrar_categoria_saude(df)
    assert sorted(saude["Classe"].tolist()) == [0.0, 0.0, 1.0]
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'prepara_fakerecogna'`

- [ ] **Step 4: Implementar o mínimo**

Criar `scripts/prepara_fakerecogna.py`:

```python
"""Gera o recorte de saúde do FakeRecogna, reextraindo o texto original.

O FakeRecogna (recogna-nlp/FakeRecogna, Hugging Face, MIT) traz o texto da
notícia já lematizado pelos autores originais — inutilizável para treino
junto com o Fake.br (texto natural), porque o modelo aprenderia a diferença
de registro textual entre os dois datasets em vez de desinformação. Por
isso este script usa a tabela só como índice (URL + rótulo) e reextrai o
texto real via `ingestao.extrair_noticia`, a mesma função que já serve a
etapa [0] do pipeline.

Uso: python scripts/prepara_fakerecogna.py
"""

import pandas as pd

CATEGORIA_SAUDE = "saúde"


def ler_fakerecogna(caminho_parquet) -> pd.DataFrame:
    """Lê o parquet do FakeRecogna, mantendo só as colunas usadas pelo recorte."""
    df = pd.read_parquet(caminho_parquet)
    return df[["Titulo", "Noticia", "Categoria", "URL", "Classe"]]


def filtrar_categoria_saude(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só as linhas de categoria 'saúde'."""
    return df[df["Categoria"] == CATEGORIA_SAUDE].copy()
```

- [ ] **Step 5: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/fakerecogna_mini.parquet tests/test_prepara_fakerecogna.py scripts/prepara_fakerecogna.py
git commit -m "test: leitura e filtro de categoria do parquet FakeRecogna"
```

---

## Task 2: Reextração de texto via URL e montagem do CSV de saída

**Files:**
- Modify: `scripts/prepara_fakerecogna.py`
- Modify: `tests/test_prepara_fakerecogna.py`

**Interfaces:**
- Consome: `verdade_ou_fake.ingestao.extrair_noticia(url: str) -> Noticia | None` (já existe)
- Produz: `reextrair_textos(df: pd.DataFrame, extrair: Callable[[str], "Noticia | None"]) -> pd.DataFrame` com colunas `["id_par", "texto", "rotulo", "categoria", "fonte"]`
- Produz: `taxa_de_extracao(total: int, sucesso: int) -> float`

`reextrair_textos` recebe `extrair` como parâmetro injetável — mesmo padrão de `buscar` em `pipeline.py` — para que o teste rode sem rede, passando uma função falsa.

- [ ] **Step 1: Escrever o teste falho**

Primeiro, atualizar a linha de import no topo de `tests/test_prepara_fakerecogna.py`
(deixada pela Task 1) para incluir os dois nomes novos usados pelos testes desta
tarefa:

```python
from prepara_fakerecogna import (
    filtrar_categoria_saude,
    ler_fakerecogna,
    reextrair_textos,
    taxa_de_extracao,
)
```

Depois, adicionar ao final de `tests/test_prepara_fakerecogna.py`:

```python
from verdade_ou_fake.tipos import Noticia


def _extrator_falso_com_sucesso(url: str):
    return Noticia(url=url, titulo="t", texto="corpo da notícia recuperado", dominio="exemplo.invalid")


def _extrator_falso_que_sempre_falha(url: str):
    return None


def _extrator_falso_parcial(url: str):
    if "cancer" in url:
        return None
    return Noticia(url=url, titulo="t", texto="corpo recuperado", dominio="exemplo.invalid")


def test_reextrai_texto_e_monta_schema_compativel():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_com_sucesso)
    assert list(resultado.columns) == ["id_par", "texto", "rotulo", "categoria", "fonte"]
    assert len(resultado) == 3
    assert set(resultado["fonte"]) == {"fakerecogna"}
    assert set(resultado["categoria"]) == {"saúde"}


def test_descarta_linhas_cuja_extracao_falha():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_que_sempre_falha)
    assert len(resultado) == 0


def test_extracao_parcial_mantem_so_as_que_tiveram_sucesso():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_parcial)
    assert len(resultado) == 2


def test_taxa_de_extracao_calcula_percentual():
    assert taxa_de_extracao(total=4, sucesso=3) == 0.75
    assert taxa_de_extracao(total=4, sucesso=0) == 0.0


def test_taxa_de_extracao_com_total_zero_nao_divide_por_zero():
    assert taxa_de_extracao(total=0, sucesso=0) == 0.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: FAIL com `ImportError: cannot import name 'reextrair_textos'`

- [ ] **Step 3: Implementar**

Adicionar a `scripts/prepara_fakerecogna.py`:

```python
from collections.abc import Callable
from pathlib import Path

from verdade_ou_fake.tipos import Noticia

ExtratorDeNoticia = Callable[[str], "Noticia | None"]


def reextrair_textos(df: pd.DataFrame, extrair: ExtratorDeNoticia) -> pd.DataFrame:
    """Reextrai o texto original de cada URL, descartando as que falharem.

    O campo `Noticia` do FakeRecogna vem lematizado pelos autores originais
    e não é usado — só a URL e a Classe (rótulo) servem de índice. Isso evita
    que o modelo aprenda a diferença de registro textual entre o Fake.br
    (texto natural) e o FakeRecogna, em vez de sinal de desinformação.

    Mapeamento de rótulo: no FakeRecogna, `Classe == 0.0` significa "fake" e
    `Classe == 1.0` significa "real" — invertido em relação à convenção do
    projeto (`rotulo == 1` é desinformação, `rotulo == 0` é legítima). Por
    isso `rotulo = 1 - int(Classe)`.
    """
    linhas = []
    for _, linha in df.iterrows():
        noticia = extrair(linha["URL"])
        if noticia is None:
            continue
        linhas.append(
            {
                "id_par": f"fakerecogna-{len(linhas)}",
                "texto": noticia.texto,
                "rotulo": 1 - int(linha["Classe"]),
                "categoria": linha["Categoria"],
                "fonte": "fakerecogna",
            }
        )
    return pd.DataFrame(linhas, columns=["id_par", "texto", "rotulo", "categoria", "fonte"])


def taxa_de_extracao(total: int, sucesso: int) -> float:
    """Percentual de URLs que renderam texto aproveitável."""
    if total == 0:
        return 0.0
    return sucesso / total
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: 8 passed

- [ ] **Step 5: Verificar manualmente o mapeamento de rótulo com a fixture**

A fixture tem `Classe=[0.0, 1.0, 0.0, 0.0]` para `["vacina-autismo", "campanha-vacinacao", "ator-morto" (entretenimento, filtrado), "cha-boldo-cancer"]`. Após filtrar saúde e reextrair com o extrator de sucesso total, a notícia "vacina-autismo" (Classe 0.0 = fake) deve virar `rotulo=1` (desinformação), e "campanha-vacinacao" (Classe 1.0 = real) deve virar `rotulo=0`. Adicionar este teste de regressão:

```python
def test_mapeia_classe_fakerecogna_para_rotulo_do_projeto():
    df = filtrar_categoria_saude(ler_fakerecogna(FIXTURE))
    resultado = reextrair_textos(df, extrair=_extrator_falso_com_sucesso)
    # Classe 0.0 (fake) -> rotulo 1 (desinformação); Classe 1.0 (real) -> rotulo 0
    linha_vacina = df[df["URL"].str.contains("vacina-autismo")].iloc[0]
    assert linha_vacina["Classe"] == 0.0
    linha_campanha = df[df["URL"].str.contains("campanha-vacinacao")].iloc[0]
    assert linha_campanha["Classe"] == 1.0
    assert set(resultado["rotulo"]) == {0, 1}
```

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/prepara_fakerecogna.py tests/test_prepara_fakerecogna.py
git commit -m "feat: reextrai texto original do FakeRecogna via URL preservada"
```

---

## Task 3: Script executável, hash de integridade e datasheet

**Files:**
- Modify: `scripts/prepara_fakerecogna.py`
- Modify: `tests/test_prepara_fakerecogna.py`
- Modify: `dados/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produz: `impressao_digital_parquet(caminho: Path) -> str` (sha256 do conteúdo do arquivo)
- Produz: `main() -> None` (ponto de entrada do script)

- [ ] **Step 1: Escrever o teste falho para o hash**

Adicionar a `tests/test_prepara_fakerecogna.py`:

```python
import hashlib


def test_impressao_digital_e_deterministica():
    assert impressao_digital_parquet(FIXTURE) == impressao_digital_parquet(FIXTURE)


def test_impressao_digital_muda_se_o_arquivo_mudar(tmp_path):
    copia = tmp_path / "fakerecogna.parquet"
    copia.write_bytes(FIXTURE.read_bytes() + b"\x00")
    assert impressao_digital_parquet(copia) != impressao_digital_parquet(FIXTURE)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: FAIL com `ImportError: cannot import name 'impressao_digital_parquet'`

- [ ] **Step 3: Implementar o hash e o `main()`**

Adicionar a `scripts/prepara_fakerecogna.py`:

```python
import hashlib
import sys

from verdade_ou_fake.ingestao import extrair_noticia

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

URL_PARQUET = "https://huggingface.co/api/datasets/recogna-nlp/FakeRecogna/parquet/default/train/0.parquet"
CAMINHO_PARQUET_LOCAL = RAIZ / "dados" / "raw" / "fakerecogna.parquet"
CAMINHO_SAIDA = RAIZ / "dados" / "processed" / "saude_fakerecogna.csv"


def impressao_digital_parquet(caminho: Path) -> str:
    """SHA-256 do conteúdo do parquet, para registrar no model card."""
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def main() -> None:
    import requests

    CAMINHO_PARQUET_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if not CAMINHO_PARQUET_LOCAL.exists():
        print(f"Baixando {URL_PARQUET}")
        resposta = requests.get(URL_PARQUET, timeout=120)
        resposta.raise_for_status()
        CAMINHO_PARQUET_LOCAL.write_bytes(resposta.content)

    hash_parquet = impressao_digital_parquet(CAMINHO_PARQUET_LOCAL)
    print(f"Hash do parquet: {hash_parquet}")

    df = filtrar_categoria_saude(ler_fakerecogna(CAMINHO_PARQUET_LOCAL))
    print(f"Notícias de saúde no FakeRecogna: {len(df)}")

    resultado = reextrair_textos(df, extrair=extrair_noticia)
    taxa = taxa_de_extracao(total=len(df), sucesso=len(resultado))
    print(f"Taxa de extração bem-sucedida: {taxa:.1%} ({len(resultado)}/{len(df)})")
    print(resultado["rotulo"].value_counts().to_string(), "\n")

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(CAMINHO_SAIDA, index=False)
    print(f"Salvo em {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_prepara_fakerecogna.py -v`
Expected: 11 passed

- [ ] **Step 5: Ajustar `.gitignore`**

O projeto hoje ignora `dados/processed/` inteiro. Por decisão do usuário, o CSV do
FakeRecogna é commitado (não é regenerável em segundos como o Fake.br, que baixa de
um commit fixo em segundos). Editar `.gitignore`:

```
dados/raw/
dados/processed/
!dados/processed/saude_fakerecogna.csv
modelos/
*.joblib
.pytest_cache/
```

- [ ] **Step 6: Reservar a seção do datasheet (sem números ainda)**

Adicionar a `dados/README.md`, após a seção `## Limitações conhecidas`:

```markdown
## Segunda fonte: FakeRecogna (Onda 2)

**Origem:** [recogna-nlp/FakeRecogna](https://huggingface.co/datasets/recogna-nlp/FakeRecogna)
(Hugging Face, licença MIT), categoria "saúde" (4.456 notícias na fonte original).

**Por que não usar o texto da tabela direto:** o campo `Noticia` vem lematizado
pelo pipeline de pré-processamento dos autores originais (ex.: "o governar
federal contar logístico" em vez de "o governo conta com a logística"). Misturar
isso com o texto natural do Fake.br ensinaria o modelo a distinguir o *dataset de
origem*, não fake/real. Em vez disso, `scripts/prepara_fakerecogna.py` usa a
tabela como índice (URL + rótulo) e reextrai o texto original via
`ingestao.extrair_noticia` — a mesma função que já serve a etapa [0] do pipeline.

**Como gerar:**

```bash
python scripts/prepara_fakerecogna.py
```

Saída: `dados/processed/saude_fakerecogna.csv`, commitado no git (diferente do
`saude_ptbr.csv`, que é regenerado em segundos a partir de um commit fixo do
Fake.br — o FakeRecogna depende de milhares de requisições de rede a sites de
terceiros, não regenerável a cada execução do CI).

**Mapeamento de rótulo:** no FakeRecogna, `Classe=0.0` é falsa e `Classe=1.0` é
real — invertido em relação à convenção do projeto (`rotulo=1` é desinformação).
O script já faz essa conversão.

**Volume e taxa de extração:** _preencher após rodar `scripts/prepara_fakerecogna.py`
pela primeira vez — não prometer números antes de medir._
```

- [ ] **Step 7: Commit**

```bash
git add scripts/prepara_fakerecogna.py tests/test_prepara_fakerecogna.py dados/README.md .gitignore
git commit -m "feat: hash de integridade, script executável e datasheet do FakeRecogna"
```

---

## Task 4: Avaliação cross-source no treino

**Files:**
- Modify: `scripts/treina_modelo.py`
- Create: `tests/test_treino_cross_source.py`

**Interfaces:**
- Consome: `verdade_ou_fake.classificador.treinar(textos, rotulos) -> Pipeline`, `prever_risco(modelo, texto) -> float` (já existem)
- Produz: `avaliar_cross_source(df: pd.DataFrame, treinar_fn, metrica_fn) -> dict` com chaves `"fakebr_para_fakerecogna"` e `"fakerecogna_para_fakebr"` (cada uma `float | None`)

A função recebe `treinar_fn` e `metrica_fn` injetáveis para que o teste rode rápido,
sem treinar um `LogisticRegression` real em cada chamada — mesmo padrão de injeção
de dependência usado em `pipeline.py` para `buscar`.

- [ ] **Step 1: Escrever o teste falho**

Criar `tests/test_treino_cross_source.py`:

```python
import pandas as pd
import pytest

from treina_modelo import avaliar_cross_source

DF_DUAS_FONTES = pd.DataFrame({
    "id_par": ["1", "2", "3", "4"],
    "texto": ["a", "b", "c", "d"],
    "rotulo": [1, 0, 1, 0],
    "fonte": ["fakebr", "fakebr", "fakerecogna", "fakerecogna"],
})

DF_SO_FAKEBR = pd.DataFrame({
    "id_par": ["1", "2"],
    "texto": ["a", "b"],
    "rotulo": [1, 0],
    "fonte": ["fakebr", "fakebr"],
})


def _treinar_fn_falso(textos, rotulos):
    return {"treinado_com": len(textos)}


def _metrica_fn_falsa(modelo, textos, rotulos):
    return 0.7


def test_avalia_nas_duas_direcoes_quando_ambas_fontes_presentes():
    resultado = avaliar_cross_source(DF_DUAS_FONTES, _treinar_fn_falso, _metrica_fn_falsa)
    assert resultado["fakebr_para_fakerecogna"] == 0.7
    assert resultado["fakerecogna_para_fakebr"] == 0.7


def test_devolve_none_quando_falta_uma_fonte():
    resultado = avaliar_cross_source(DF_SO_FAKEBR, _treinar_fn_falso, _metrica_fn_falsa)
    assert resultado["fakebr_para_fakerecogna"] is None
    assert resultado["fakerecogna_para_fakebr"] is None


def test_treina_so_com_os_dados_da_fonte_de_origem():
    chamadas = []

    def treinar_fn_espiao(textos, rotulos):
        chamadas.append(len(textos))
        return {}

    avaliar_cross_source(DF_DUAS_FONTES, treinar_fn_espiao, _metrica_fn_falsa)
    # 2 notícias fakebr treinando p/ testar em fakerecogna, depois 2 fakerecogna p/ testar em fakebr
    assert chamadas == [2, 2]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_treino_cross_source.py -v`
Expected: FAIL com `ModuleNotFoundError` ou `ImportError: cannot import name 'avaliar_cross_source'`

- [ ] **Step 3: Implementar**

Adicionar a `scripts/treina_modelo.py` (antes de `main()`):

```python
from collections.abc import Callable

TreinarFn = Callable[[list[str], list[int]], object]
MetricaFn = Callable[[object, list[str], list[int]], float]


def avaliar_cross_source(
    df: pd.DataFrame, treinar_fn: TreinarFn, metrica_fn: MetricaFn
) -> dict[str, float | None]:
    """Mede o viés de fonte: treina numa fonte, testa na outra.

    Um modelo que aprendeu o estilo editorial do portal (em vez de sinais de
    desinformação) terá F1 alto na mesma fonte e baixo na fonte oposta. Exige
    as duas fontes presentes em `df["fonte"]`; se faltar uma, devolve None nas
    duas direções em vez de comparar parcialmente.
    """
    fontes = set(df["fonte"].unique())
    if not {"fakebr", "fakerecogna"} <= fontes:
        return {"fakebr_para_fakerecogna": None, "fakerecogna_para_fakebr": None}

    fakebr = df[df["fonte"] == "fakebr"]
    fakerecogna = df[df["fonte"] == "fakerecogna"]

    modelo_fakebr = treinar_fn(fakebr["texto"].tolist(), fakebr["rotulo"].tolist())
    f1_fakebr_para_fakerecogna = metrica_fn(
        modelo_fakebr, fakerecogna["texto"].tolist(), fakerecogna["rotulo"].tolist()
    )

    modelo_fakerecogna = treinar_fn(fakerecogna["texto"].tolist(), fakerecogna["rotulo"].tolist())
    f1_fakerecogna_para_fakebr = metrica_fn(
        modelo_fakerecogna, fakebr["texto"].tolist(), fakebr["rotulo"].tolist()
    )

    return {
        "fakebr_para_fakerecogna": f1_fakebr_para_fakerecogna,
        "fakerecogna_para_fakebr": f1_fakerecogna_para_fakebr,
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_treino_cross_source.py -v`
Expected: 3 passed

- [ ] **Step 5: Integrar ao `main()` de `treina_modelo.py`**

Modificar `scripts/treina_modelo.py:22-45` (função `main`) para também carregar o
FakeRecogna se existir, rodar `avaliar_cross_source`, e imprimir o resultado:

```python
from pathlib import Path
from sklearn.metrics import f1_score

CAMINHO_DADOS_FAKERECOGNA = RAIZ / "dados" / "processed" / "saude_fakerecogna.csv"


def _f1_macro(modelo, textos, rotulos) -> float:
    previsto = modelo.predict(textos)
    return f1_score(rotulos, previsto, average="macro")


def main() -> None:
    df = pd.read_csv(CAMINHO_DADOS, dtype={"id_par": str})
    df["fonte"] = "fakebr"
    print(f"Notícias (Fake.br): {len(df)}")
    print(df["rotulo"].value_counts(), "\n")

    divisor = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    indices_treino, indices_teste = next(divisor.split(df, groups=df["id_par"]))
    treino, teste = df.iloc[indices_treino], df.iloc[indices_teste]
    treino_x, treino_y = treino["texto"].tolist(), treino["rotulo"].tolist()
    teste_x, teste_y = teste["texto"].tolist(), teste["rotulo"].tolist()

    modelo = treinar(treino_x, treino_y)
    previsto = modelo.predict(teste_x)

    print("=== Relatório de classificação ===")
    print(classification_report(teste_y, previsto, target_names=["legítima", "desinformação"]))
    print("=== Matriz de confusão ===")
    print(confusion_matrix(teste_y, previsto))

    f1_same_source = f1_score(teste_y, previsto, average="macro")
    print(f"F1 macro (same-source): {f1_same_source:.3f}\n")

    cross_source = {"fakebr_para_fakerecogna": None, "fakerecogna_para_fakebr": None}
    if CAMINHO_DADOS_FAKERECOGNA.exists():
        df_fakerecogna = pd.read_csv(CAMINHO_DADOS_FAKERECOGNA, dtype={"id_par": str})
        df_combinado = pd.concat([df, df_fakerecogna], ignore_index=True)
        cross_source = avaliar_cross_source(df_combinado, treinar, _f1_macro)
        print("=== Avaliação cross-source (viés de fonte) ===")
        print(f"Treina Fake.br -> testa FakeRecogna: {cross_source['fakebr_para_fakerecogna']}")
        print(f"Treina FakeRecogna -> testa Fake.br: {cross_source['fakerecogna_para_fakebr']}\n")
    else:
        print(
            f"Aviso: {CAMINHO_DADOS_FAKERECOGNA} não encontrado — avaliação cross-source "
            "pulada. Rode scripts/prepara_fakerecogna.py para habilitá-la.\n"
        )

    salvar(modelo, CAMINHO_MODELO)
    print(f"Modelo salvo em {CAMINHO_MODELO}")
```

- [ ] **Step 6: Rodar a suíte inteira e ver passar**

Run: `venv/bin/python -m pytest -m "not rede" -q`
Expected: todos os testes existentes continuam passando, mais os novos desta tarefa

- [ ] **Step 7: Commit**

```bash
git add scripts/treina_modelo.py tests/test_treino_cross_source.py
git commit -m "feat: avaliação cross-source mede viés de fonte no treino"
```

---

## Task 5: Módulo `model_card.py`

**Files:**
- Create: `src/verdade_ou_fake/model_card.py`
- Create: `tests/test_model_card.py`

**Interfaces:**
- Produz: `calcular_hash_artefato(caminho: Path) -> str`
- Produz: `montar_card(nome, tipo, commit, dados, metricas, limiar_aprovacao, artefato_hash, treinado_em, treinado_por) -> dict`
- Produz: `aprovar_gate(card: dict) -> bool`
- Produz: `salvar_card(card: dict, caminho: Path) -> None`
- Produz: `carregar_card(caminho: Path) -> dict`

- [ ] **Step 1: Escrever o teste falho para `calcular_hash_artefato`**

Criar `tests/test_model_card.py`:

```python
from pathlib import Path

from verdade_ou_fake.model_card import (
    aprovar_gate,
    calcular_hash_artefato,
    carregar_card,
    montar_card,
    salvar_card,
)


def test_hash_e_deterministico_para_o_mesmo_arquivo(tmp_path):
    arquivo = tmp_path / "modelo.joblib"
    arquivo.write_bytes(b"conteudo do modelo")
    assert calcular_hash_artefato(arquivo) == calcular_hash_artefato(arquivo)


def test_hash_muda_se_o_conteudo_mudar(tmp_path):
    arquivo = tmp_path / "modelo.joblib"
    arquivo.write_bytes(b"conteudo original")
    hash_original = calcular_hash_artefato(arquivo)
    arquivo.write_bytes(b"conteudo alterado")
    assert calcular_hash_artefato(arquivo) != hash_original
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'verdade_ou_fake.model_card'`

- [ ] **Step 3: Implementar `calcular_hash_artefato`**

Criar `src/verdade_ou_fake/model_card.py`:

```python
"""Versiona treino, métricas e artefato de modelo em JSON, no git.

Substitui o .joblib solto em disco sem metadata associada: cada treino
produz um card em `modelos/cards/<nome>.json` com hash de integridade,
métricas (incluindo cross-source, para detectar viés de fonte) e o gate de
aprovação que decide se o modelo pode ser promovido a produção.
"""

import hashlib
import json
from pathlib import Path


def calcular_hash_artefato(caminho: Path) -> str:
    """SHA-256 do conteúdo do artefato do modelo (arquivo ou diretório)."""
    caminho = Path(caminho)
    hash_ = hashlib.sha256()
    if caminho.is_dir():
        for arquivo in sorted(caminho.rglob("*")):
            if arquivo.is_file():
                hash_.update(arquivo.relative_to(caminho).as_posix().encode("utf-8"))
                hash_.update(arquivo.read_bytes())
    else:
        hash_.update(caminho.read_bytes())
    return hash_.hexdigest()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: 2 passed

- [ ] **Step 5: Escrever o teste falho para `montar_card`, `salvar_card`, `carregar_card`**

Adicionar a `tests/test_model_card.py`:

```python
def _card_valido(**sobrescritas) -> dict:
    base = dict(
        nome="baseline",
        tipo="tfidf_logreg",
        commit="abc1234",
        dados={
            "fontes": ["fakebr"],
            "hash_fakebr": "x" * 64,
            "hash_fakerecogna": None,
            "volume_treino": 280,
            "volume_teste": 70,
        },
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        },
        limiar_aprovacao={
            "f1_macro_same_source_minimo": 0.75,
            "queda_maxima_cross_source": 0.20,
        },
        artefato_hash="y" * 64,
        treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
    )
    base.update(sobrescritas)
    return montar_card(**base)


def test_montar_card_produz_status_staging_por_padrao():
    card = _card_valido()
    assert card["status"] == "staging"
    assert card["nome"] == "baseline"


def test_salva_e_recarrega_preservando_o_conteudo(tmp_path):
    card = _card_valido()
    caminho = tmp_path / "baseline.json"
    salvar_card(card, caminho)
    recarregado = carregar_card(caminho)
    assert recarregado == card
```

- [ ] **Step 6: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: FAIL com `ImportError: cannot import name 'montar_card'`

- [ ] **Step 7: Implementar `montar_card`, `salvar_card`, `carregar_card`**

Adicionar a `src/verdade_ou_fake/model_card.py`:

```python
def montar_card(
    nome: str,
    tipo: str,
    commit: str,
    dados: dict,
    metricas: dict,
    limiar_aprovacao: dict,
    artefato_hash: str,
    treinado_em: str,
    treinado_por: str,
    status: str = "staging",
) -> dict:
    """Monta o dicionário do model card a partir dos dados de um treino."""
    return {
        "nome": nome,
        "versao": f"{treinado_em[:10]}-{commit[:7]}",
        "tipo": tipo,
        "commit": commit,
        "dados": dados,
        "metricas": metricas,
        "limiar_aprovacao": limiar_aprovacao,
        "status": status,
        "artefato_hash_sha256": artefato_hash,
        "treinado_em": treinado_em,
        "treinado_por": treinado_por,
    }


def salvar_card(card: dict, caminho: Path) -> None:
    """Serializa o model card em disco, formatado para diff legível."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(card, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def carregar_card(caminho: Path) -> dict:
    """Carrega um model card salvo por `salvar_card`."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))
```

- [ ] **Step 8: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: 4 passed

- [ ] **Step 9: Escrever o teste falho para `aprovar_gate`**

Adicionar a `tests/test_model_card.py` — cobre o Review Focus "model card com
métricas ausentes" (gate deve reprovar, nunca aprovar por omissão nem lançar
exceção):

```python
def test_aprova_quando_f1_acima_do_minimo_e_sem_queda_cross_source():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.75,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.70,
        }
    )
    assert aprovar_gate(card) is True


def test_reprova_quando_f1_same_source_abaixo_do_minimo():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.60,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        }
    )
    assert aprovar_gate(card) is False


def test_reprova_quando_queda_cross_source_excede_o_limiar():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.90,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.50,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.55,
        }
    )
    assert aprovar_gate(card) is False


def test_aprova_no_limite_exato_da_queda_permitida():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.80,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.60,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.60,
        }
    )
    # queda = 0.80 - 0.60 = 0.20, igual ao limiar -> deve aprovar
    assert aprovar_gate(card) is True


def test_aprova_sem_avaliar_cross_source_quando_metricas_sao_none():
    # Cross-source ainda não calculado (ex.: FakeRecogna não gerado) não deve
    # reprovar por omissão -- só a condição de F1 same-source é exigida.
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        }
    )
    assert aprovar_gate(card) is True
```

- [ ] **Step 10: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: FAIL com `ImportError: cannot import name 'aprovar_gate'`

- [ ] **Step 11: Implementar `aprovar_gate`**

Adicionar a `src/verdade_ou_fake/model_card.py`:

```python
def aprovar_gate(card: dict) -> bool:
    """Decide se o modelo pode ser promovido a produção.

    Duas condições: o F1 same-source precisa atingir o mínimo configurado, e a
    queda do F1 para o F1 cross-source (quando calculado) não pode exceder o
    limiar — essa segunda condição é o que detecta viés de fonte: um modelo
    que decorou o portal de origem tem F1 alto na mesma fonte e baixo na
    fonte oposta. Métricas cross-source ausentes (None) não reprovam o gate
    por omissão -- só avalia a condição quando o dado existe.
    """
    metricas = card["metricas"]
    limiar = card["limiar_aprovacao"]

    if metricas["f1_macro_same_source"] < limiar["f1_macro_same_source_minimo"]:
        return False

    quedas = [
        metricas["f1_macro_same_source"] - valor_cross
        for chave, valor_cross in metricas.items()
        if chave.startswith("f1_macro_cross_source") and valor_cross is not None
    ]
    if any(queda > limiar["queda_maxima_cross_source"] for queda in quedas):
        return False

    return True
```

- [ ] **Step 12: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_model_card.py -v`
Expected: 9 passed

- [ ] **Step 13: Commit**

```bash
git add src/verdade_ou_fake/model_card.py tests/test_model_card.py
git commit -m "feat: módulo model_card com hash de integridade e gate de aprovação"
```

---

## Task 6: `app.py` valida o model card antes de servir

**Files:**
- Modify: `app.py`
- Create: `tests/test_app_model_card.py`

**Interfaces:**
- Consome: `verdade_ou_fake.model_card.carregar_card`, `calcular_hash_artefato` (Task 5)
- Produz: `validar_modelo_para_producao(caminho_card: Path, caminho_artefato: Path) -> tuple[bool, str]` em um novo módulo `src/verdade_ou_fake/model_card.py` (a mesma função do Task 5, estendida)

`app.py` é interface Streamlit sem teste automatizado de UI (igual ao resto do
projeto — ver Task 9 do plano original). A lógica de validação, porém, é pura e
testável isoladamente antes de ser chamada pelo `app.py`.

- [ ] **Step 1: Escrever o teste falho**

Criar `tests/test_app_model_card.py`:

```python
from pathlib import Path

from verdade_ou_fake.model_card import montar_card, salvar_card, validar_modelo_para_producao


def _card_producao(artefato_hash: str) -> dict:
    return montar_card(
        nome="baseline",
        tipo="tfidf_logreg",
        commit="abc1234",
        dados={"fontes": ["fakebr"], "hash_fakebr": "x" * 64, "hash_fakerecogna": None,
               "volume_treino": 280, "volume_teste": 70},
        metricas={"f1_macro_same_source": 0.81,
                  "f1_macro_cross_source_fakebr_para_fakerecogna": None,
                  "f1_macro_cross_source_fakerecogna_para_fakebr": None},
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash=artefato_hash,
        treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
        status="producao",
    )


def test_valida_com_sucesso_quando_hash_bate_e_status_e_producao(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")
    from verdade_ou_fake.model_card import calcular_hash_artefato
    hash_real = calcular_hash_artefato(artefato)

    card = _card_producao(hash_real)
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is True


def test_reprova_quando_hash_nao_bate(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")

    card = _card_producao(artefato_hash="hash_errado" + "0" * 50)
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is False
    assert "hash" in mensagem.lower()


def test_reprova_quando_status_nao_e_producao(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")
    from verdade_ou_fake.model_card import calcular_hash_artefato
    hash_real = calcular_hash_artefato(artefato)

    card = _card_producao(hash_real)
    card["status"] = "staging"
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is False
    assert "status" in mensagem.lower() or "produção" in mensagem.lower()


def test_reprova_quando_card_nao_existe(tmp_path):
    ok, mensagem = validar_modelo_para_producao(tmp_path / "inexistente.json", tmp_path / "modelo.joblib")
    assert ok is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_app_model_card.py -v`
Expected: FAIL com `ImportError: cannot import name 'validar_modelo_para_producao'`

- [ ] **Step 3: Implementar**

Adicionar a `src/verdade_ou_fake/model_card.py`:

```python
def validar_modelo_para_producao(caminho_card: Path, caminho_artefato: Path) -> tuple[bool, str]:
    """Confere que o artefato em disco corresponde ao model card de produção.

    Usado por `app.py` antes de carregar o modelo: evita servir silenciosamente
    um modelo desatualizado (card trocado sem retreinar) ou corrompido (hash
    não bate). Retorna (True, "") em sucesso, (False, motivo) em falha.
    """
    caminho_card = Path(caminho_card)
    if not caminho_card.exists():
        return False, f"Model card não encontrado em {caminho_card}."

    card = carregar_card(caminho_card)

    if card["status"] != "producao":
        return False, f"Model card tem status '{card['status']}', esperado 'producao'."

    hash_atual = calcular_hash_artefato(caminho_artefato)
    if hash_atual != card["artefato_hash_sha256"]:
        return False, (
            "Hash do artefato em disco não corresponde ao registrado no model card — "
            "o modelo pode ter sido retreinado sem atualizar o card, ou está corrompido."
        )

    return True, ""
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_app_model_card.py -v`
Expected: 4 passed

- [ ] **Step 5: Integrar ao `app.py`**

Modificar `app.py:14-45` (imports e checagem de existência do modelo):

```python
from verdade_ou_fake.classificador import carregar
from verdade_ou_fake.model_card import validar_modelo_para_producao
from verdade_ou_fake.pipeline import analisar_link
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"
CAMINHO_MODEL_CARD = RAIZ / "modelos" / "cards" / "baseline.json"
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"

CORES = {"alta": "🟢", "media": "🟡", "baixa": "⚪"}


@st.cache_resource
def carregar_recursos():
    """Carrega modelo e vocabulário uma única vez por sessão."""
    return carregar(CAMINHO_MODELO), carregar_vocabulario(CAMINHO_VOCABULARIO)


st.set_page_config(page_title="Verdade ou Fake?", page_icon="🔍")

st.title("🔍 Verdade ou Fake?")
st.caption("Checagem de notícias sobre medicamentos e tratamentos")

st.warning(
    "**Este sistema é apenas informativo e não substitui orientação médica.** "
    "As respostas são uma síntese de evidências públicas, não uma prescrição."
)

if not CAMINHO_MODELO.exists():
    st.error(
        f"Modelo não encontrado em `{CAMINHO_MODELO}`. "
        "Rode `python scripts/treina_modelo.py` antes de iniciar a interface."
    )
    st.stop()

modelo_ok, motivo = validar_modelo_para_producao(CAMINHO_MODEL_CARD, CAMINHO_MODELO)
if not modelo_ok:
    st.error(f"Modelo não validado para produção: {motivo}")
    st.stop()
```

O restante do `app.py` (a partir de `modelo, vocabulario = carregar_recursos()`)
permanece inalterado.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `venv/bin/python -m pytest -m "not rede" -q`
Expected: todos os testes passam, incluindo os novos desta tarefa

- [ ] **Step 7: Commit**

```bash
git add app.py src/verdade_ou_fake/model_card.py tests/test_app_model_card.py
git commit -m "feat: app.py valida model card e hash antes de servir o modelo"
```

---

## Task 7: Script `verifica_gate.py` e geração do card no treino

**Files:**
- Modify: `scripts/treina_modelo.py`
- Create: `scripts/verifica_gate.py`
- Create: `tests/test_verifica_gate.py`

**Interfaces:**
- Consome: `verdade_ou_fake.model_card.carregar_card`, `aprovar_gate` (Task 5)
- Produz: `main(caminho_card: str) -> int` (código de saída: 0 aprovado, 1 reprovado)

- [ ] **Step 1: Escrever o teste falho**

Criar `tests/test_verifica_gate.py`:

```python
from pathlib import Path

from verdade_ou_fake.model_card import montar_card, salvar_card
from verifica_gate import main


def _card(f1_same_source: float, tmp_path: Path) -> Path:
    card = montar_card(
        nome="baseline", tipo="tfidf_logreg", commit="abc1234",
        dados={"fontes": ["fakebr"], "hash_fakebr": "x" * 64, "hash_fakerecogna": None,
               "volume_treino": 280, "volume_teste": 70},
        metricas={"f1_macro_same_source": f1_same_source,
                  "f1_macro_cross_source_fakebr_para_fakerecogna": None,
                  "f1_macro_cross_source_fakerecogna_para_fakebr": None},
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash="y" * 64, treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
    )
    caminho = tmp_path / "baseline.json"
    salvar_card(card, caminho)
    return caminho


def test_sai_com_codigo_zero_quando_aprova(tmp_path):
    caminho = _card(f1_same_source=0.81, tmp_path=tmp_path)
    assert main(str(caminho)) == 0


def test_sai_com_codigo_um_quando_reprova(tmp_path):
    caminho = _card(f1_same_source=0.50, tmp_path=tmp_path)
    assert main(str(caminho)) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `venv/bin/python -m pytest tests/test_verifica_gate.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'verifica_gate'`

- [ ] **Step 3: Implementar**

Criar `scripts/verifica_gate.py`:

```python
"""Verifica se um model card passa no gate de qualidade — usado pelo CI.

Uso: python scripts/verifica_gate.py modelos/cards/baseline.json
Saída: código 0 se aprovado, 1 se reprovado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.model_card import aprovar_gate, carregar_card


def main(caminho_card: str) -> int:
    card = carregar_card(Path(caminho_card))
    aprovado = aprovar_gate(card)
    if aprovado:
        print(f"Gate aprovado: F1 same-source = {card['metricas']['f1_macro_same_source']:.3f}")
        return 0
    print(f"Gate reprovado: {card['metricas']}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `venv/bin/python -m pytest tests/test_verifica_gate.py -v`
Expected: 2 passed

- [ ] **Step 5: Gerar o model card ao final do treino**

Modificar `scripts/treina_modelo.py`. Primeiro, adicionar aos imports do topo do
arquivo:

```python
import subprocess
from datetime import datetime

from verdade_ou_fake.model_card import calcular_hash_artefato, montar_card, salvar_card

CAMINHO_CARD = RAIZ / "modelos" / "cards" / "baseline.json"


def _commit_atual() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "desconhecido"
```

Depois, localizar a linha `salvar(modelo, CAMINHO_MODELO)` já existente dentro de
`main()` (adicionada na Task 4, Step 5) e acrescentar a geração do card logo
**depois** dela, sem duplicar a chamada existente:

```python
    salvar(modelo, CAMINHO_MODELO)
    print(f"Modelo salvo em {CAMINHO_MODELO}")

    card = montar_card(
        nome="baseline",
        tipo="tfidf_logreg",
        commit=_commit_atual(),
        dados={
            "fontes": ["fakebr"] if not CAMINHO_DADOS_FAKERECOGNA.exists() else ["fakebr", "fakerecogna"],
            "hash_fakebr": None,
            "hash_fakerecogna": None,
            "volume_treino": len(treino_x),
            "volume_teste": len(teste_x),
        },
        metricas={
            "f1_macro_same_source": f1_same_source,
            "f1_macro_cross_source_fakebr_para_fakerecogna": cross_source["fakebr_para_fakerecogna"],
            "f1_macro_cross_source_fakerecogna_para_fakebr": cross_source["fakerecogna_para_fakebr"],
        },
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash=calcular_hash_artefato(CAMINHO_MODELO),
        treinado_em=datetime.now().astimezone().isoformat(),
        treinado_por="scripts/treina_modelo.py",
    )
    salvar_card(card, CAMINHO_CARD)
    print(f"Model card salvo em {CAMINHO_CARD}")
```

- [ ] **Step 6: Rodar a suíte inteira**

Run: `venv/bin/python -m pytest -m "not rede" -q`
Expected: todos os testes passam

- [ ] **Step 7: Commit**

```bash
git add scripts/verifica_gate.py scripts/treina_modelo.py tests/test_verifica_gate.py
git commit -m "feat: gera model card ao final do treino e verifica gate de qualidade"
```

---

## Task 8: Workflows GitHub Actions

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/treino-gate.yml`
- Create: `.github/workflows/prepara-fakerecogna.yml`

Esta tarefa não tem teste automatizado — workflows do GitHub Actions só são
validados rodando no GitHub. A verificação é manual, descrita no Step 4.

- [ ] **Step 1: Criar o CI rápido**

Criar `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest -m "not rede" -q
```

- [ ] **Step 2: Criar o gate de treino (automático, sem FakeRecogna)**

Criar `.github/workflows/treino-gate.yml`:

```yaml
name: Treino Gate

on:
  workflow_dispatch:
  push:
    paths:
      - 'dados/vocabulario_seed.csv'
      - 'src/verdade_ou_fake/classificador.py'
      - 'src/verdade_ou_fake/fusao.py'
      - 'dados/processed/saude_fakerecogna.csv'

jobs:
  treino:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python scripts/prepara_dataset.py
      - run: python scripts/treina_modelo.py
      - name: Verificar gate de qualidade
        run: python scripts/verifica_gate.py modelos/cards/baseline.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: model-card-staging
          path: modelos/cards/baseline.json
```

Nota sobre o design (documentar como comentário no topo do arquivo): este
workflow **não roda `prepara_fakerecogna.py`** — a extração via rede de ~4.456
URLs de terceiros não deve repetir a cada push. Se `dados/processed/saude_fakerecogna.csv`
já existir no repositório (gerado manualmente, ver próximo workflow), o treino o
usa automaticamente para a avaliação cross-source; caso contrário, o treino roda
só com o Fake.br e avisa que o cross-source foi pulado (comportamento já
implementado na Task 4, Step 5).

- [ ] **Step 3: Criar o workflow manual de extração do FakeRecogna**

Criar `.github/workflows/prepara-fakerecogna.yml`:

```yaml
name: Prepara FakeRecogna (manual)

on:
  workflow_dispatch:

jobs:
  extrair:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python scripts/prepara_fakerecogna.py
      - uses: actions/upload-artifact@v4
        with:
          name: saude-fakerecogna-csv
          path: dados/processed/saude_fakerecogna.csv
```

Este workflow só roda por acionamento manual (`workflow_dispatch`), nunca por
push — reflete a decisão de manter a extração via rede fora da automação por
push. O CSV resultante sobe como artifact para um humano baixar e commitar no
PR, mantendo a decisão de versionamento sob revisão humana.

- [ ] **Step 4: Verificação manual**

Depois de dar push desta branch ao GitHub:

1. Confirmar que `ci.yml` roda automaticamente e passa (verde) na aba Actions.
2. Disparar `treino-gate.yml` manualmente (botão "Run workflow" na aba Actions)
   e confirmar que ele treina, gera o card, roda o gate e sobe o artifact.
3. Disparar `prepara-fakerecogna.yml` manualmente uma vez e confirmar que ele
   sobe o CSV como artifact (pode demorar — são milhares de requisições de rede).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/treino-gate.yml .github/workflows/prepara-fakerecogna.yml
git commit -m "ci: workflows de teste rápido, gate de treino e extração manual do FakeRecogna"
```

---

## Task 9: Atualizar documentação de arquitetura

**Files:**
- Modify: `docs/arquitetura.md`
- Modify: `README.md`

- [ ] **Step 1: Adicionar seção de MLOps a `docs/arquitetura.md`**

Adicionar ao final de `docs/arquitetura.md`, após a seção `## Stack técnica`:

```markdown
## MLOps

A partir da revisão contra Kreuzberger, Kühl & Hirschl (*MLOps: Overview,
Definition, and Architecture*, arXiv:2205.02302), o projeto adota uma versão
leve dos componentes do artigo, dimensionada para equipe pequena e orçamento
zero:

| Princípio do artigo | Implementação neste projeto |
|---|---|
| P1 — CI/CD automation | `.github/workflows/ci.yml` roda a suíte de testes a cada push/PR |
| P4 — Versioning (modelo) | `modelos/cards/*.json`, versionado no git, com hash de integridade do artefato |
| P6 — Continuous training | `.github/workflows/treino-gate.yml`, acionável manualmente ou por mudança em código/vocabulário relevante |
| P7 — ML metadata tracking | Métricas, dados de origem e limiares de aprovação registrados no model card |

**Por que não um model registry remoto.** Decisão deliberada: um arquivo JSON
versionado no git é legível em diff por qualquer membro da equipe sem rodar
nada, e não exige hospedar um servidor — coerente com o orçamento zero do
projeto. Fica como possível evolução futura se a equipe crescer.

**Gate de qualidade com detecção de viés de fonte.** Além do F1 macro
same-source já existente, o treino mede F1 cross-source (treina numa fonte de
dados, testa na outra) — a assinatura de um modelo que aprendeu o portal de
origem em vez de desinformação é F1 alto same-source e baixo cross-source. Um
modelo só é promovido a `status: producao` se a queda entre os dois não
exceder o limiar configurado no card. Ver
`src/verdade_ou_fake/model_card.py:aprovar_gate`.
```

- [ ] **Step 2: Atualizar "Como rodar" no `README.md`**

Modificar a seção `## Como rodar` do `README.md` para incluir o novo script:

```markdown
## Como rodar

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python scripts/prepara_dataset.py       # gera o recorte de saúde (Fake.br)
python scripts/prepara_fakerecogna.py   # opcional: gera a 2ª fonte (FakeRecogna) — demorado, faz milhares de requisições de rede
python scripts/treina_modelo.py         # treina, avalia (incl. cross-source se a 2ª fonte existir) e gera o model card
streamlit run app.py                    # abre a interface

pytest                                  # roda os testes
pytest -m "not rede"                    # roda os testes sem tocar a rede (CI offline)
```
```

- [ ] **Step 3: Commit**

```bash
git add docs/arquitetura.md README.md
git commit -m "docs: documenta MLOps, gate de qualidade e segunda fonte de dados"
```

---

## Definição de pronto

- [ ] `pytest -m "not rede"` passa inteiro, sem nenhum teste tocando a rede
- [ ] `pytest` (suíte completa, incluindo os marcados `rede`) passa
- [ ] `scripts/prepara_fakerecogna.py` roda manualmente ao menos uma vez e gera `dados/processed/saude_fakerecogna.csv` com taxa de extração registrada no datasheet
- [ ] `scripts/treina_modelo.py` gera `modelos/cards/baseline.json` com métricas same-source e cross-source (quando a 2ª fonte existe)
- [ ] `app.py` recusa servir um modelo cujo card não está em `status: producao` ou cujo hash não bate
- [ ] `.github/workflows/ci.yml` roda e passa no GitHub Actions
- [ ] `.github/workflows/treino-gate.yml` roda manualmente e produz um model card como artifact
- [ ] `docs/arquitetura.md` e `README.md` documentam a arquitetura MLOps resultante
