# Plano de Implementação — Fase 1 (PoC)

> **Para trabalhadores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam
> checkbox (`- [ ]`) para rastreamento.

**Objetivo:** construir a fatia vertical fina que atravessa as quatro etapas do
sistema — link → texto → classificador → evidência → veredito na tela.

**Arquitetura:** cada etapa é um módulo isolado com uma responsabilidade e interface
definida em `tipos.py`. A lógica pura (parsing, regras, filtros) é separada do I/O
(rede, disco), de modo que os testes rodem **sem internet**. O `pipeline.py` costura
tudo; a interface Streamlit só chama o pipeline.

**Stack:** Python 3.11 · trafilatura · requests · pandas · scikit-learn · joblib ·
Streamlit · pytest

**Spec:** [Arquitetura](arquitetura.md) e [Fontes de Dados](dados.md)

## Restrições globais

- **Python 3.11+** — a sintaxe `tipo | None` exige 3.10 no mínimo.
- **Orçamento zero** — nenhuma dependência de API paga, em nenhuma tarefa.
- **Testes sem rede** — nenhum teste pode fazer requisição HTTP. Toda função que acessa rede é dividida em uma parte pura (testada) e uma casca fina de I/O (não testada em unidade).
- **Português no código** — nomes de funções, variáveis e mensagens em português, seguindo o que já existe na documentação. Termos técnicos consagrados (`fit`, `predict`, `TF-IDF`) permanecem em inglês.
- **Commits em português**, prefixo convencional (`feat:`, `test:`, `docs:`, `chore:`).
- **Um commit por tarefa concluída**, no mínimo.

## Como usar este plano

Cada tarefa é independente o suficiente para uma pessoa pegar sozinha. O ciclo em toda
tarefa é o mesmo — **escreve o teste, vê ele falhar, implementa, vê passar, commita**.
Ver o teste falhar não é burocracia: é o que prova que o teste realmente testa alguma
coisa.

**Ordem e paralelismo:**

```
Task 1 (todos, juntos)
   │
   ├──→ Task 2 (Frente D) ──┐
   ├──→ Task 3 (Frente C) ──┤
   │       └→ Task 4 (Frente C) ──┤
   ├──→ Task 5 (Frente A) ──┐     │
   │       └→ Task 6 (Frente B) ──┤
   └──→ Task 7 (Frente D) ────────┤
                                  ▼
                            Task 8 (integração, juntos)
                                  │
                                  ▼
                            Task 9 (Frente D)
```

Depois da Task 1, as tarefas 2, 3, 5 e 7 começam **ao mesmo tempo**. A Task 1 precisa
ser feita primeiro e por todos juntos, porque ela define os contratos (`tipos.py`) de
que todas as outras dependem.

| Frente | Responsável | Tarefas |
|---|---|---|
| A — Dados | *a definir* | 5 |
| B — Modelo | *a definir* | 6 |
| C — Evidência | *a definir* | 3, 4 |
| D — Produto | *a definir* | 2, 7, 9 |

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/verdade_ou_fake/tipos.py` | Contratos compartilhados. Nenhuma lógica. |
| `src/verdade_ou_fake/ingestao.py` | Etapa [0]: link → texto limpo |
| `src/verdade_ou_fake/vocabulario.py` | Etapa [2a]: dicionário e extração do par medicamento+condição |
| `src/verdade_ou_fake/evidencia.py` | Etapa [2b]: busca no PubMed |
| `src/verdade_ou_fake/classificador.py` | Etapa [1]: treino e inferência do baseline |
| `src/verdade_ou_fake/fusao.py` | Etapa [3]: regras de combinação |
| `src/verdade_ou_fake/pipeline.py` | Orquestra as etapas |
| `scripts/prepara_dataset.py` | Filtra o recorte de saúde do corpus |
| `dados/vocabulario_seed.csv` | Dicionário inicial PT→EN |
| `app.py` | Interface Streamlit |
| `tests/` | Um arquivo de teste por módulo |

!!! warning "O que a PoC **não** faz"
    A Camada 2c da PoC **não distingue "apoia" de "contradiz"** — isso exige o modelo
    de NLI, que é Fase 2. Aqui ela responde apenas **encontrou literatura** ou **não
    cobre**, com força medida pelo tipo de estudo. Isso é deliberado: a fatia fina
    prova que o caminho funciona, não que ele já está bom.

---

## Task 1: Estrutura do projeto e contratos

**Todos juntos.** Ninguém começa a sua frente antes disso existir.

**Arquivos:**

- Criar: `requirements.txt`, `pytest.ini`, `src/verdade_ou_fake/__init__.py`, `src/verdade_ou_fake/tipos.py`
- Criar: `tests/__init__.py`, `tests/test_tipos.py`
- Modificar: `.gitignore`

**Interfaces:**

- Produz: as dataclasses `Noticia`, `Alegacao`, `Artigo`, `Evidencia`, `Veredito`. **Todas as tarefas seguintes consomem estes tipos.**

- [ ] **Passo 1: Criar `requirements.txt`**

```
trafilatura>=2.0
requests>=2.32
pandas>=2.2
scikit-learn>=1.5
joblib>=1.4
datasets>=3.0
streamlit>=1.40
pytest>=8.0
```

Versões com `>=` para não travar na instalação. Depois que todo mundo tiver o ambiente
funcionando, rodem `pip freeze > requirements.lock.txt` para congelar.

- [ ] **Passo 2: Criar o ambiente e instalar**

```bash
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

- [ ] **Passo 3: Configurar o pytest**

Criar `pytest.ini`:

```ini
[pytest]
pythonpath = src
testpaths = tests
```

A linha `pythonpath = src` é o que permite escrever `from verdade_ou_fake import ...`
nos testes sem instalar o pacote.

- [ ] **Passo 4: Atualizar `.gitignore`**

Acrescentar ao final do arquivo:

```
dados/raw/
dados/processed/
modelos/
*.joblib
.pytest_cache/
```

Dados brutos e modelos treinados **não vão para o git** — são grandes e regeneráveis.
O que vai é o script que os gera.

- [ ] **Passo 5: Escrever o teste dos contratos**

Criar `tests/test_tipos.py`:

```python
from verdade_ou_fake.tipos import Noticia, Alegacao, Artigo, Evidencia, Veredito


def test_noticia_guarda_os_campos_extraidos():
    noticia = Noticia(
        url="https://exemplo.com/materia",
        titulo="Remédio milagroso",
        texto="Corpo da matéria.",
        dominio="exemplo.com",
    )
    assert noticia.dominio == "exemplo.com"
    assert noticia.titulo == "Remédio milagroso"


def test_alegacao_guarda_os_termos_nos_dois_idiomas():
    alegacao = Alegacao(
        medicamento_pt="ivermectina",
        medicamento_en="Ivermectin",
        condicao_pt="covid-19",
        condicao_en="COVID-19",
    )
    assert alegacao.medicamento_en == "Ivermectin"


def test_evidencia_sem_artigos_significa_nao_coberta():
    evidencia = Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
    assert evidencia.artigos == []
    assert evidencia.cobertura == "nao_cobre"


def test_artigo_guarda_o_tipo_de_estudo():
    artigo = Artigo(
        pmid="12345",
        titulo="A randomized trial",
        resumo="Resumo do estudo.",
        tipos_estudo=["Randomized Controlled Trial"],
        ano=2021,
    )
    assert "Randomized Controlled Trial" in artigo.tipos_estudo


def test_veredito_carrega_a_explicacao_para_o_usuario():
    veredito = Veredito(
        rotulo="Não foi possível verificar",
        confianca="baixa",
        risco_textual=0.8,
        alegacao=None,
        evidencia=None,
        explicacao="Não identificamos medicamento e condição no texto.",
    )
    assert veredito.confianca == "baixa"
```

- [ ] **Passo 6: Rodar e ver falhar**

```bash
pytest tests/test_tipos.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake'`.

- [ ] **Passo 7: Implementar os contratos**

Criar `src/verdade_ou_fake/__init__.py` vazio e `src/verdade_ou_fake/tipos.py`:

```python
"""Contratos compartilhados entre as etapas do pipeline.

Este módulo não tem lógica — só define os formatos de dado que as etapas
trocam entre si. Alterar algo aqui afeta todas as frentes, então mudanças
devem ser combinadas com o time.
"""

from dataclasses import dataclass, field


@dataclass
class Noticia:
    """Resultado da etapa [0] — texto limpo extraído do link."""

    url: str
    titulo: str
    texto: str
    dominio: str


@dataclass
class Alegacao:
    """Resultado da etapa [2a] — o par medicamento + condição encontrado no texto.

    Guarda os termos nos dois idiomas: o português é o que apareceu na notícia,
    o inglês é o que será usado na busca ao PubMed.
    """

    medicamento_pt: str
    medicamento_en: str
    condicao_pt: str
    condicao_en: str


@dataclass
class Artigo:
    """Um artigo científico recuperado do PubMed."""

    pmid: str
    titulo: str
    resumo: str
    tipos_estudo: list[str]
    ano: int | None


@dataclass
class Evidencia:
    """Resultado da etapa [2] — o que a literatura diz sobre a alegação.

    cobertura: "encontrada" ou "nao_cobre"
    forca: "forte" (revisão sistemática ou meta-análise),
           "moderada" (ensaio clínico randomizado),
           "fraca" (demais tipos),
           "nenhuma" (nada encontrado)

    Na Fase 1 não distinguimos "apoia" de "contradiz" — isso exige o modelo
    de NLI previsto para a Fase 2.
    """

    cobertura: str
    forca: str
    artigos: list[Artigo] = field(default_factory=list)


@dataclass
class Veredito:
    """Resultado final da etapa [3] — o que o usuário vê."""

    rotulo: str
    confianca: str
    risco_textual: float
    alegacao: Alegacao | None
    evidencia: Evidencia | None
    explicacao: str
```

- [ ] **Passo 8: Rodar e ver passar**

```bash
pytest tests/test_tipos.py -v
```

Esperado: **5 passed**.

- [ ] **Passo 9: Commit**

```bash
git add requirements.txt pytest.ini .gitignore src/ tests/
git commit -m "feat: estrutura do projeto e contratos compartilhados"
```

---

## Task 2: Ingestão — do link ao texto

**Frente D.** Depende da Task 1.

**Arquivos:**

- Criar: `src/verdade_ou_fake/ingestao.py`, `tests/test_ingestao.py`, `tests/fixtures/noticia_exemplo.html`

**Interfaces:**

- Consome: `Noticia` de `tipos.py`
- Produz: `extrair_de_html(html: str, url: str) -> Noticia | None` e `extrair_noticia(url: str) -> Noticia | None`

A função é dividida em duas de propósito: `extrair_de_html` é **pura** (recebe texto,
devolve objeto) e é a que testamos; `extrair_noticia` só adiciona o download. Assim os
testes rodam sem internet.

- [ ] **Passo 1: Criar a fixture de HTML**

Criar `tests/fixtures/noticia_exemplo.html`:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head><title>Portal de Teste</title></head>
<body>
  <nav>Menu | Esportes | Política</nav>
  <div class="cookie-banner">Aceite nossos cookies</div>
  <article>
    <h1>Estudo aponta que ivermectina cura covid-19 em 2 dias</h1>
    <p>Pesquisadores afirmam que o medicamento ivermectina teria efeito
    imediato contra a covid-19, segundo publicação recente.</p>
    <p>O composto já é usado como antiparasitário há décadas.</p>
  </article>
  <aside>Leia também: outras 10 notícias</aside>
  <footer>Copyright Portal de Teste</footer>
</body>
</html>
```

- [ ] **Passo 2: Escrever o teste falho**

Criar `tests/test_ingestao.py`:

```python
from pathlib import Path

from verdade_ou_fake.ingestao import extrair_de_html

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def test_extrai_o_corpo_da_materia():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/materia")
    assert noticia is not None
    assert "ivermectina" in noticia.texto.lower()
    assert "antiparasitário" in noticia.texto.lower()


def test_descarta_menu_banner_e_rodape():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/materia")
    assert noticia is not None
    texto = noticia.texto.lower()
    assert "aceite nossos cookies" not in texto
    assert "copyright" not in texto
    assert "leia também" not in texto


def test_guarda_o_dominio_de_origem():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/saude/materia")
    assert noticia is not None
    assert noticia.dominio == "portal.exemplo.com"


def test_html_sem_conteudo_devolve_none():
    noticia = extrair_de_html("<html><body></body></html>", "https://x.com/a")
    assert noticia is None
```

- [ ] **Passo 3: Rodar e ver falhar**

```bash
pytest tests/test_ingestao.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.ingestao'`.

- [ ] **Passo 4: Implementar**

Criar `src/verdade_ou_fake/ingestao.py`:

```python
"""Etapa [0] — transforma o link de uma notícia em texto limpo.

A extração é dividida em duas funções: `extrair_de_html` é pura e testável,
`extrair_noticia` acrescenta o download. Essa separação é o que permite testar
sem internet.
"""

from urllib.parse import urlparse

import requests
import trafilatura

from verdade_ou_fake.tipos import Noticia

TAMANHO_MINIMO = 100
TIMEOUT_SEGUNDOS = 15


def extrair_de_html(html: str, url: str) -> Noticia | None:
    """Extrai o conteúdo principal de uma página já baixada.

    Devolve None quando não há corpo de texto aproveitável — página vazia,
    paywall ou layout que o trafilatura não reconhece.
    """
    texto = trafilatura.extract(html, include_comments=False, include_tables=False)
    if not texto or len(texto) < TAMANHO_MINIMO:
        return None

    metadados = trafilatura.extract_metadata(html)
    titulo = metadados.title if metadados and metadados.title else ""

    return Noticia(
        url=url,
        titulo=titulo,
        texto=texto,
        dominio=urlparse(url).netloc,
    )


def extrair_noticia(url: str) -> Noticia | None:
    """Baixa a página e extrai o conteúdo. Devolve None se o download falhar."""
    try:
        resposta = requests.get(
            url,
            timeout=TIMEOUT_SEGUNDOS,
            headers={"User-Agent": "VerdadeOuFake/0.1 (projeto academico UnB)"},
        )
        resposta.raise_for_status()
    except requests.RequestException:
        return None

    return extrair_de_html(resposta.text, url)
```

- [ ] **Passo 5: Rodar e ver passar**

```bash
pytest tests/test_ingestao.py -v
```

Esperado: **4 passed**.

- [ ] **Passo 6: Validar contra a realidade (decisão D4)**

Este passo não é teste automatizado — é a validação da hipótese D4 da
[Arquitetura](arquitetura.md).

Criar `scripts/testa_extracao.py`:

```python
"""Roda a extração contra links reais e reporta a taxa de sucesso.

Uso: python scripts/testa_extracao.py links.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from verdade_ou_fake.ingestao import extrair_noticia

def main(caminho_lista: str) -> None:
    links = Path(caminho_lista).read_text(encoding="utf-8").split()
    sucessos = 0
    for link in links:
        noticia = extrair_noticia(link)
        if noticia is None:
            print(f"FALHOU  {link}")
        else:
            sucessos += 1
            print(f"OK      {link} ({len(noticia.texto)} chars) — {noticia.titulo[:60]}")
    print(f"\nTaxa de extração: {sucessos}/{len(links)}")


if __name__ == "__main__":
    main(sys.argv[1])
```

Montar `links.txt` com **20 links reais** de notícias de saúde, de portais diferentes,
e rodar. Anotar a taxa no [Canvas](canva.md) como resposta à GQ8. Se a taxa ficar
abaixo de 70%, acionar o plano B da decisão D4.

- [ ] **Passo 7: Commit**

```bash
git add src/verdade_ou_fake/ingestao.py tests/test_ingestao.py tests/fixtures/ scripts/testa_extracao.py
git commit -m "feat: extração de texto limpo a partir do link da notícia"
```

---

## Task 3: Vocabulário e extração da alegação

**Frente C.** Depende da Task 1.

**Arquivos:**

- Criar: `dados/vocabulario_seed.csv`, `src/verdade_ou_fake/vocabulario.py`, `tests/test_vocabulario.py`

**Interfaces:**

- Consome: `Alegacao` de `tipos.py`
- Produz: `carregar_vocabulario(caminho: Path) -> dict[str, list[tuple[str, str]]]` e `extrair_alegacao(texto: str, vocabulario: dict) -> Alegacao | None`

!!! note "Por que um CSV semente e não o DeCS"
    O acesso ao DeCS para download em massa é a decisão **D1**, ainda não validada. O
    CSV semente com ~35 termos desbloqueia o desenvolvimento agora; ampliar com o DeCS
    é tarefa da Fase 2. A função de carga já recebe o caminho como parâmetro, então
    trocar a fonte depois não exige mudar nada além do arquivo.

- [ ] **Passo 1: Criar o vocabulário semente**

Criar `dados/vocabulario_seed.csv`:

```csv
termo_pt,termo_en,tipo
hidroxicloroquina,Hydroxychloroquine,medicamento
cloroquina,Chloroquine,medicamento
ivermectina,Ivermectin,medicamento
azitromicina,Azithromycin,medicamento
dipirona,Dipyrone,medicamento
paracetamol,Acetaminophen,medicamento
ibuprofeno,Ibuprofen,medicamento
dexametasona,Dexamethasone,medicamento
prednisona,Prednisone,medicamento
metformina,Metformin,medicamento
insulina,Insulin,medicamento
omeprazol,Omeprazole,medicamento
amoxicilina,Amoxicillin,medicamento
vitamina d,Vitamin D,medicamento
vitamina c,Ascorbic Acid,medicamento
zinco,Zinc,medicamento
melatonina,Melatonin,medicamento
sinvastatina,Simvastatin,medicamento
losartana,Losartan,medicamento
fluoxetina,Fluoxetine,medicamento
canabidiol,Cannabidiol,medicamento
semaglutida,Semaglutide,medicamento
nimesulida,Nimesulide,medicamento
covid-19,COVID-19,condicao
covid,COVID-19,condicao
diabetes,Diabetes Mellitus,condicao
hipertensao,Hypertension,condicao
cancer,Neoplasms,condicao
depressao,Depressive Disorder,condicao
ansiedade,Anxiety Disorders,condicao
obesidade,Obesity,condicao
alzheimer,Alzheimer Disease,condicao
artrite,Arthritis,condicao
asma,Asthma,condicao
dengue,Dengue,condicao
gripe,"Influenza, Human",condicao
enxaqueca,Migraine Disorders,condicao
autismo,Autism Spectrum Disorder,condicao
```

- [ ] **Passo 2: Escrever o teste falho**

Criar `tests/test_vocabulario.py`:

```python
from pathlib import Path

from verdade_ou_fake.vocabulario import carregar_vocabulario, extrair_alegacao, normalizar

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"


def test_normalizar_remove_acento_e_caixa():
    assert normalizar("Hipertensão") == "hipertensao"
    assert normalizar("COVID-19") == "covid-19"


def test_carregar_separa_medicamentos_de_condicoes():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    assert "medicamento" in vocabulario
    assert "condicao" in vocabulario
    assert ("ivermectina", "Ivermectin") in vocabulario["medicamento"]
    assert ("covid-19", "COVID-19") in vocabulario["condicao"]


def test_extrai_o_par_quando_ambos_aparecem():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Estudo aponta que a ivermectina cura covid-19 em dois dias."
    alegacao = extrair_alegacao(texto, vocabulario)
    assert alegacao is not None
    assert alegacao.medicamento_en == "Ivermectin"
    assert alegacao.condicao_en == "COVID-19"


def test_encontra_termos_com_acento_e_maiuscula():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Nova pesquisa sobre Metformina no tratamento da Hipertensão."
    alegacao = extrair_alegacao(texto, vocabulario)
    assert alegacao is not None
    assert alegacao.medicamento_en == "Metformin"
    assert alegacao.condicao_en == "Hypertension"


def test_devolve_none_quando_falta_o_medicamento():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Casos de dengue aumentam na região metropolitana."
    assert extrair_alegacao(texto, vocabulario) is None


def test_devolve_none_quando_falta_a_condicao():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "Preço da dipirona sobe 12% nas farmácias."
    assert extrair_alegacao(texto, vocabulario) is None


def test_nao_casa_termo_dentro_de_outra_palavra():
    vocabulario = carregar_vocabulario(CAMINHO_VOCABULARIO)
    texto = "O zincógrafo é uma máquina antiga usada contra a dengue."
    assert extrair_alegacao(texto, vocabulario) is None
```

O último teste é o mais importante: sem fronteira de palavra, `"zinco"` casaria dentro
de `"zincógrafo"` e o sistema inventaria alegações que não existem.

- [ ] **Passo 3: Rodar e ver falhar**

```bash
pytest tests/test_vocabulario.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.vocabulario'`.

- [ ] **Passo 4: Implementar**

Criar `src/verdade_ou_fake/vocabulario.py`:

```python
"""Etapa [2a] — identifica o par medicamento + condição no texto da notícia.

Usa casamento por dicionário controlado em vez de um modelo de NER: o domínio
é fechado (medicamentos e doenças têm nomes oficiais) e o dicionário é
auditável, o que um modelo treinado não seria.
"""

import csv
import re
import unicodedata
from pathlib import Path

from verdade_ou_fake.tipos import Alegacao


def normalizar(texto: str) -> str:
    """Remove acentos e coloca em minúsculas, para casar 'Hipertensão' com 'hipertensao'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def carregar_vocabulario(caminho: Path) -> dict[str, list[tuple[str, str]]]:
    """Lê o CSV e agrupa os termos por tipo.

    Devolve {"medicamento": [(termo_pt, termo_en), ...], "condicao": [...]}.
    Os termos em português vêm normalizados; os em inglês, como estão.
    """
    vocabulario: dict[str, list[tuple[str, str]]] = {"medicamento": [], "condicao": []}
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            tipo = linha["tipo"]
            if tipo in vocabulario:
                vocabulario[tipo].append((normalizar(linha["termo_pt"]), linha["termo_en"]))
    return vocabulario


def _primeiro_termo_presente(
    texto_normalizado: str, termos: list[tuple[str, str]]
) -> tuple[str, str] | None:
    """Devolve o primeiro par (pt, en) cujo termo aparece como palavra inteira.

    Os termos são ordenados do mais longo para o mais curto para que
    'vitamina d' seja testado antes de eventuais termos contidos nele.
    """
    for termo_pt, termo_en in sorted(termos, key=lambda par: -len(par[0])):
        padrao = r"\b" + re.escape(termo_pt) + r"\b"
        if re.search(padrao, texto_normalizado):
            return termo_pt, termo_en
    return None


def extrair_alegacao(texto: str, vocabulario: dict[str, list[tuple[str, str]]]) -> Alegacao | None:
    """Procura um medicamento e uma condição no texto.

    Devolve None se faltar qualquer um dos dois — sem o par não há o que
    consultar no PubMed.
    """
    texto_normalizado = normalizar(texto)

    medicamento = _primeiro_termo_presente(texto_normalizado, vocabulario["medicamento"])
    condicao = _primeiro_termo_presente(texto_normalizado, vocabulario["condicao"])

    if medicamento is None or condicao is None:
        return None

    return Alegacao(
        medicamento_pt=medicamento[0],
        medicamento_en=medicamento[1],
        condicao_pt=condicao[0],
        condicao_en=condicao[1],
    )
```

- [ ] **Passo 5: Rodar e ver passar**

```bash
pytest tests/test_vocabulario.py -v
```

Esperado: **7 passed**.

- [ ] **Passo 6: Commit**

```bash
git add dados/vocabulario_seed.csv src/verdade_ou_fake/vocabulario.py tests/test_vocabulario.py
git commit -m "feat: extração do par medicamento+condição por vocabulário controlado"
```

---

## Task 4: Busca de evidência no PubMed

**Frente C.** Depende da Task 1. Pode ser feita em paralelo com a Task 3.

**Arquivos:**

- Criar: `src/verdade_ou_fake/evidencia.py`, `tests/test_evidencia.py`, `tests/fixtures/pubmed_resposta.xml`

**Interfaces:**

- Consome: `Alegacao`, `Artigo`, `Evidencia` de `tipos.py`
- Produz: `parsear_artigos(xml: str) -> list[Artigo]`, `classificar_forca(artigos: list[Artigo]) -> str`, `montar_evidencia(artigos: list[Artigo]) -> Evidencia`, `buscar_evidencia(alegacao: Alegacao) -> Evidencia`

Mesma divisão da Task 2: as três primeiras funções são puras e testadas;
`buscar_evidencia` é a casca com rede.

- [ ] **Passo 1: Criar a fixture da resposta do PubMed**

Criar `tests/fixtures/pubmed_resposta.xml`:

```xml
<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>33473311</PMID>
      <Article>
        <ArticleTitle>Ivermectin for preventing and treating COVID-19</ArticleTitle>
        <Abstract>
          <AbstractText>We assessed the efficacy of ivermectin in COVID-19.</AbstractText>
        </Abstract>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Systematic Review</PublicationType>
          <PublicationType>Meta-Analysis</PublicationType>
        </PublicationTypeList>
      </Article>
      <DateCompleted><Year>2021</Year></DateCompleted>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>34145166</PMID>
      <Article>
        <ArticleTitle>A randomized trial of ivermectin in mild COVID-19</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Trial background.</AbstractText>
          <AbstractText Label="RESULTS">No significant difference was found.</AbstractText>
        </Abstract>
        <PublicationTypeList>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
      <DateCompleted><Year>2022</Year></DateCompleted>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
```

- [ ] **Passo 2: Escrever o teste falho**

Criar `tests/test_evidencia.py`:

```python
from pathlib import Path

from verdade_ou_fake.evidencia import (
    classificar_forca,
    montar_evidencia,
    montar_query,
    parsear_artigos,
)
from verdade_ou_fake.tipos import Alegacao, Artigo

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_xml() -> str:
    return (FIXTURES / "pubmed_resposta.xml").read_text(encoding="utf-8")


def artigo(tipos: list[str]) -> Artigo:
    return Artigo(pmid="1", titulo="t", resumo="r", tipos_estudo=tipos, ano=2020)


def test_monta_query_com_os_termos_em_ingles():
    alegacao = Alegacao(
        medicamento_pt="ivermectina",
        medicamento_en="Ivermectin",
        condicao_pt="covid-19",
        condicao_en="COVID-19",
    )
    assert montar_query(alegacao) == '"Ivermectin"[MeSH Terms] AND "COVID-19"[MeSH Terms]'


def test_parseia_os_dois_artigos_da_resposta():
    artigos = parsear_artigos(carregar_xml())
    assert len(artigos) == 2
    assert artigos[0].pmid == "33473311"
    assert artigos[0].ano == 2021


def test_parseia_titulo_e_tipos_de_estudo():
    artigos = parsear_artigos(carregar_xml())
    assert "Ivermectin" in artigos[0].titulo
    assert "Meta-Analysis" in artigos[0].tipos_estudo
    assert artigos[1].tipos_estudo == ["Randomized Controlled Trial"]


def test_junta_as_secoes_do_resumo():
    artigos = parsear_artigos(carregar_xml())
    assert "Trial background." in artigos[1].resumo
    assert "No significant difference was found." in artigos[1].resumo


def test_xml_vazio_devolve_lista_vazia():
    assert parsear_artigos("<PubmedArticleSet></PubmedArticleSet>") == []


def test_revisao_sistematica_e_forca_forte():
    assert classificar_forca([artigo(["Systematic Review"])]) == "forte"
    assert classificar_forca([artigo(["Meta-Analysis"])]) == "forte"


def test_ensaio_randomizado_e_forca_moderada():
    assert classificar_forca([artigo(["Randomized Controlled Trial"])]) == "moderada"


def test_demais_tipos_sao_forca_fraca():
    assert classificar_forca([artigo(["Case Reports"])]) == "fraca"


def test_sem_artigos_a_forca_e_nenhuma():
    assert classificar_forca([]) == "nenhuma"


def test_a_forca_e_a_do_melhor_artigo_encontrado():
    artigos = [artigo(["Case Reports"]), artigo(["Systematic Review"])]
    assert classificar_forca(artigos) == "forte"


def test_evidencia_sem_artigos_e_nao_cobre():
    evidencia = montar_evidencia([])
    assert evidencia.cobertura == "nao_cobre"
    assert evidencia.forca == "nenhuma"


def test_evidencia_com_artigos_e_encontrada():
    evidencia = montar_evidencia(parsear_artigos(carregar_xml()))
    assert evidencia.cobertura == "encontrada"
    assert evidencia.forca == "forte"
    assert len(evidencia.artigos) == 2
```

- [ ] **Passo 3: Rodar e ver falhar**

```bash
pytest tests/test_evidencia.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.evidencia'`.

- [ ] **Passo 4: Implementar**

Criar `src/verdade_ou_fake/evidencia.py`:

```python
"""Etapa [2b] — busca literatura científica sobre a alegação no PubMed.

Usa a API E-utilities do NCBI, que é gratuita e não exige chave. O parsing do
XML fica em funções puras, testadas com uma resposta gravada; só
`buscar_evidencia` toca a rede.

Documentação da API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import xml.etree.ElementTree as ET

import requests

from verdade_ou_fake.tipos import Alegacao, Artigo, Evidencia

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT_SEGUNDOS = 20
MAX_ARTIGOS = 10

# Tipos de estudo em ordem decrescente de força de evidência.
TIPOS_FORTES = {"Systematic Review", "Meta-Analysis"}
TIPOS_MODERADOS = {"Randomized Controlled Trial"}


def montar_query(alegacao: Alegacao) -> str:
    """Monta a query do PubMed a partir dos termos em inglês.

    O sufixo [MeSH Terms] restringe a busca ao vocabulário controlado, o que
    reduz muito o ruído em comparação com busca por texto livre.
    """
    return f'"{alegacao.medicamento_en}"[MeSH Terms] AND "{alegacao.condicao_en}"[MeSH Terms]'


def _texto_do_resumo(citacao: ET.Element) -> str:
    """Junta as seções do resumo, que no PubMed vêm divididas em vários nós."""
    partes = [
        (no.text or "").strip()
        for no in citacao.iter("AbstractText")
    ]
    return " ".join(parte for parte in partes if parte)


def _ano_de_publicacao(citacao: ET.Element) -> int | None:
    no_ano = citacao.find(".//DateCompleted/Year")
    if no_ano is None or not no_ano.text:
        return None
    try:
        return int(no_ano.text)
    except ValueError:
        return None


def parsear_artigos(xml: str) -> list[Artigo]:
    """Converte a resposta XML do efetch em uma lista de Artigo."""
    raiz = ET.fromstring(xml)
    artigos: list[Artigo] = []

    for citacao in raiz.iter("MedlineCitation"):
        no_pmid = citacao.find("PMID")
        no_titulo = citacao.find(".//ArticleTitle")
        tipos = [
            (no.text or "").strip()
            for no in citacao.iter("PublicationType")
            if no.text
        ]
        artigos.append(
            Artigo(
                pmid=no_pmid.text if no_pmid is not None and no_pmid.text else "",
                titulo=no_titulo.text if no_titulo is not None and no_titulo.text else "",
                resumo=_texto_do_resumo(citacao),
                tipos_estudo=tipos,
                ano=_ano_de_publicacao(citacao),
            )
        )

    return artigos


def classificar_forca(artigos: list[Artigo]) -> str:
    """Devolve a força do melhor artigo encontrado.

    Segue a hierarquia de evidência: uma revisão sistemática vale mais que dez
    estudos isolados, então a força do conjunto é a do melhor item, não a média.
    """
    if not artigos:
        return "nenhuma"

    todos_os_tipos = {tipo for artigo in artigos for tipo in artigo.tipos_estudo}

    if todos_os_tipos & TIPOS_FORTES:
        return "forte"
    if todos_os_tipos & TIPOS_MODERADOS:
        return "moderada"
    return "fraca"


def montar_evidencia(artigos: list[Artigo]) -> Evidencia:
    """Empacota os artigos encontrados no formato que a fusão consome."""
    if not artigos:
        return Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
    return Evidencia(
        cobertura="encontrada",
        forca=classificar_forca(artigos),
        artigos=artigos,
    )


def buscar_evidencia(alegacao: Alegacao) -> Evidencia:
    """Consulta o PubMed e devolve a evidência encontrada.

    Faz duas chamadas: esearch devolve os PMIDs, efetch devolve os artigos.
    Qualquer falha de rede resulta em 'nao_cobre' — o sistema nunca afirma que
    algo é falso por não ter conseguido consultar.
    """
    try:
        resposta_busca = requests.get(
            f"{BASE_EUTILS}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": montar_query(alegacao),
                "retmode": "json",
                "retmax": MAX_ARTIGOS,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_busca.raise_for_status()
        pmids = resposta_busca.json()["esearchresult"]["idlist"]

        if not pmids:
            return montar_evidencia([])

        resposta_artigos = requests.get(
            f"{BASE_EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_artigos.raise_for_status()
    except (requests.RequestException, KeyError, ValueError):
        return montar_evidencia([])

    return montar_evidencia(parsear_artigos(resposta_artigos.text))
```

- [ ] **Passo 5: Rodar e ver passar**

```bash
pytest tests/test_evidencia.py -v
```

Esperado: **12 passed**.

- [ ] **Passo 6: Testar contra o PubMed de verdade**

No terminal, com o ambiente ativado:

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from verdade_ou_fake.evidencia import buscar_evidencia
from verdade_ou_fake.tipos import Alegacao
e = buscar_evidencia(Alegacao('ivermectina','Ivermectin','covid-19','COVID-19'))
print(e.cobertura, e.forca, len(e.artigos))
for a in e.artigos[:3]:
    print(' -', a.pmid, a.titulo[:70])
"
```

Esperado: `encontrada` e alguns artigos listados. Se vier `nao_cobre`, a query com
`[MeSH Terms]` pode estar restrita demais — anote e discuta com o time antes de
afrouxar.

- [ ] **Passo 7: Commit**

```bash
git add src/verdade_ou_fake/evidencia.py tests/test_evidencia.py tests/fixtures/pubmed_resposta.xml
git commit -m "feat: busca de evidência científica no PubMed"
```

---

## Task 5: Recorte de saúde do corpus

**Frente A.** Depende da Task 1.

**Arquivos:**

- Criar: `scripts/prepara_dataset.py`, `tests/test_prepara_dataset.py`, `dados/README.md`

**Interfaces:**

- Produz: `termos_de_saude(caminho_vocabulario: Path) -> set[str]` e `filtrar_saude(df: pd.DataFrame, coluna_texto: str, termos: set[str]) -> pd.DataFrame`

!!! warning "Inspecionar antes de filtrar"
    Os nomes das colunas do Fake.br no Hugging Face **não estão documentados aqui de
    propósito** — verifique-os no Passo 1 em vez de assumir. A função de filtro recebe
    o nome da coluna como parâmetro exatamente para que o teste não dependa disso.

- [ ] **Passo 1: Inspecionar o dataset**

```bash
python -c "
from datasets import load_dataset
ds = load_dataset('fake-news-UFG/fakebr')
print(ds)
print(ds['train'].column_names)
print(ds['train'][0])
"
```

Anote: nomes das colunas, nome da coluna de rótulo, e como as classes são
representadas (0/1? 'fake'/'true'?). Isso alimenta os passos seguintes e o
`dados/README.md`.

- [ ] **Passo 2: Escrever o teste falho**

Criar `tests/test_prepara_dataset.py`:

```python
from pathlib import Path

import pandas as pd

from prepara_dataset import filtrar_saude, termos_de_saude

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"


def test_termos_de_saude_inclui_medicamentos_e_condicoes():
    termos = termos_de_saude(CAMINHO_VOCABULARIO)
    assert "ivermectina" in termos
    assert "diabetes" in termos


def test_mantem_apenas_as_linhas_com_termo_de_saude():
    df = pd.DataFrame(
        {
            "texto": [
                "A ivermectina foi testada contra a covid-19.",
                "Prefeitura anuncia obras na avenida principal.",
                "Novo estudo sobre metformina e diabetes.",
            ],
            "rotulo": [1, 0, 0],
        }
    )
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 2
    assert "obras na avenida" not in " ".join(resultado["texto"])


def test_preserva_as_demais_colunas():
    df = pd.DataFrame({"texto": ["Estudo sobre dengue e dipirona."], "rotulo": [1]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert list(resultado.columns) == ["texto", "rotulo"]
    assert resultado.iloc[0]["rotulo"] == 1


def test_casa_ignorando_acento_e_caixa():
    df = pd.DataFrame({"texto": ["Tratamento da HIPERTENSÃO com Losartana."], "rotulo": [0]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 1


def test_dataframe_sem_saude_devolve_vazio():
    df = pd.DataFrame({"texto": ["Time vence por 3 a 0."], "rotulo": [0]})
    resultado = filtrar_saude(df, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    assert len(resultado) == 0
```

- [ ] **Passo 3: Rodar e ver falhar**

```bash
pytest tests/test_prepara_dataset.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'prepara_dataset'`.

- [ ] **Passo 4: Permitir que o pytest enxergue `scripts/`**

Alterar `pytest.ini`:

```ini
[pytest]
pythonpath = src scripts
testpaths = tests
```

- [ ] **Passo 5: Implementar**

Criar `scripts/prepara_dataset.py`:

```python
"""Extrai o recorte de saúde do corpus de notícias em português.

O corpus base (Fake.br) é de domínio geral. Este script seleciona as notícias
que mencionam algum medicamento ou condição do nosso vocabulário, produzindo o
dataset de treino da Camada 1.

Uso: python scripts/prepara_dataset.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from verdade_ou_fake.vocabulario import carregar_vocabulario, normalizar

RAIZ = Path(__file__).parent.parent
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
CAMINHO_SAIDA = RAIZ / "dados" / "processed" / "saude_ptbr.csv"


def termos_de_saude(caminho_vocabulario: Path) -> set[str]:
    """Devolve todos os termos em português do vocabulário, normalizados."""
    vocabulario = carregar_vocabulario(caminho_vocabulario)
    return {
        termo_pt
        for termos in vocabulario.values()
        for termo_pt, _ in termos
    }


def filtrar_saude(df: pd.DataFrame, coluna_texto: str, termos: set[str]) -> pd.DataFrame:
    """Mantém as linhas cujo texto menciona ao menos um termo de saúde.

    O casamento usa fronteira de palavra para não capturar termos contidos em
    outras palavras.
    """
    padrao = "|".join(r"\b" + re.escape(termo) + r"\b" for termo in termos)
    normalizados = df[coluna_texto].astype(str).map(normalizar)
    return df[normalizados.str.contains(padrao, regex=True, na=False)].copy()


def main() -> None:
    from datasets import load_dataset

    # ATENÇÃO: ajuste os nomes das colunas conforme o que você viu no Passo 1.
    coluna_texto = "text"
    coluna_rotulo = "label"

    conjunto = load_dataset("fake-news-UFG/fakebr")["train"]
    df = conjunto.to_pandas()
    print(f"Corpus completo: {len(df)} notícias")

    recorte = filtrar_saude(df, coluna_texto, termos_de_saude(CAMINHO_VOCABULARIO))
    print(f"Recorte de saúde: {len(recorte)} notícias")
    print(recorte[coluna_rotulo].value_counts())

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    recorte.to_csv(CAMINHO_SAIDA, index=False)
    print(f"Salvo em {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()
```

- [ ] **Passo 6: Rodar e ver passar**

```bash
pytest tests/test_prepara_dataset.py -v
```

Esperado: **5 passed**.

- [ ] **Passo 7: Gerar o dataset real**

```bash
python scripts/prepara_dataset.py
```

Anote os números impressos. **Se o recorte tiver menos de 300 notícias, a decisão D2
falhou** — acione a Onda 2 de coleta descrita em [Fontes de Dados](dados.md) e avise a
Frente B, que vai precisar tratar o volume baixo na avaliação.

- [ ] **Passo 8: Escrever o datasheet**

Criar `dados/README.md` com os números reais obtidos:

```markdown
# Datasheet — Recorte de saúde PT-BR

**Versão:** 1.0 · **Gerado em:** <data> · **Script:** `scripts/prepara_dataset.py`

## Origem
Fake.br Corpus (`fake-news-UFG/fakebr` no Hugging Face), corpus de notícias em
português brasileiro com rótulo verdadeira/falsa verificado manualmente.

## Critério de filtragem
Notícias que mencionam ao menos um termo de `dados/vocabulario_seed.csv`
(medicamento ou condição clínica), com casamento por fronteira de palavra,
ignorando acento e caixa.

## Volume
- Corpus completo: <n> notícias
- Recorte de saúde: <n> notícias
- Distribuição por classe: <preencher>

## Limitações conhecidas
- O corpus base é de domínio geral; o recorte de saúde é subconjunto, não amostra representativa de notícias de saúde.
- O vocabulário semente tem ~38 termos, então medicamentos fora dessa lista não são capturados.
- Possível concentração temática em COVID-19, com impacto na generalização.
- Possível viés de fonte: verificar a distribuição de domínios antes de confiar nas métricas.
```

- [ ] **Passo 9: Commit**

```bash
git add scripts/prepara_dataset.py tests/test_prepara_dataset.py dados/README.md pytest.ini
git commit -m "feat: recorte de saúde do corpus PT-BR com datasheet"
```

---

## Task 6: Classificador baseline

**Frente B.** Depende da Task 5.

**Arquivos:**

- Criar: `src/verdade_ou_fake/classificador.py`, `tests/test_classificador.py`, `scripts/treina_modelo.py`

**Interfaces:**

- Produz: `construir_modelo() -> Pipeline`, `treinar(textos, rotulos) -> Pipeline`, `salvar(modelo, caminho)`, `carregar(caminho) -> Pipeline`, `prever_risco(modelo, texto) -> float`

!!! note "Por que TF-IDF antes de BERTimbau"
    O baseline existe para ser a régua. Nenhum modelo mais complexo entra no projeto
    sem superá-lo — e é surpreendentemente comum que não supere. Treina em segundos,
    roda em CPU e é interpretável.

- [ ] **Passo 1: Escrever o teste falho**

Criar `tests/test_classificador.py`:

```python
from verdade_ou_fake.classificador import (
    carregar,
    construir_modelo,
    prever_risco,
    salvar,
    treinar,
)

TEXTOS = [
    "URGENTE!!! Médicos escondem cura milagrosa da covid-19 com ivermectina",
    "COMPARTILHE! Remédio secreto cura diabetes em 3 dias sem efeito colateral",
    "ATENÇÃO: a indústria não quer que você saiba dessa cura natural do câncer",
    "MILAGRE! Vitamina C elimina qualquer vírus, dizem especialistas ocultos",
    "Estudo publicado avalia eficácia da metformina no controle do diabetes tipo 2",
    "Pesquisa da universidade analisa uso de dexametasona em pacientes internados",
    "Ensaio clínico randomizado investiga efeito da losartana na hipertensão",
    "Revisão sistemática reúne dados sobre tratamento da asma em crianças",
]
ROTULOS = [1, 1, 1, 1, 0, 0, 0, 0]


def test_modelo_tem_vetorizador_e_classificador():
    modelo = construir_modelo()
    assert "tfidf" in modelo.named_steps
    assert "classificador" in modelo.named_steps


def test_treina_e_aprende_o_conjunto():
    modelo = treinar(TEXTOS, ROTULOS)
    assert modelo.score(TEXTOS, ROTULOS) == 1.0


def test_risco_fica_entre_zero_e_um():
    modelo = treinar(TEXTOS, ROTULOS)
    risco = prever_risco(modelo, "URGENTE! Cura milagrosa escondida pelos médicos")
    assert 0.0 <= risco <= 1.0


def test_texto_sensacionalista_tem_risco_maior_que_texto_sobrio():
    modelo = treinar(TEXTOS, ROTULOS)
    sensacionalista = prever_risco(
        modelo, "URGENTE!!! COMPARTILHE: cura milagrosa secreta que a indústria esconde"
    )
    sobrio = prever_risco(
        modelo, "Estudo publicado avalia a eficácia do tratamento em ensaio clínico"
    )
    assert sensacionalista > sobrio


def test_salva_e_carrega_preservando_a_previsao(tmp_path):
    modelo = treinar(TEXTOS, ROTULOS)
    caminho = tmp_path / "modelo.joblib"
    salvar(modelo, caminho)

    recarregado = carregar(caminho)
    texto = "Cura milagrosa da diabetes revelada"
    assert prever_risco(recarregado, texto) == prever_risco(modelo, texto)
```

- [ ] **Passo 2: Rodar e ver falhar**

```bash
pytest tests/test_classificador.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.classificador'`.

- [ ] **Passo 3: Implementar**

Criar `src/verdade_ou_fake/classificador.py`:

```python
"""Etapa [1] — classificador de risco textual (baseline).

TF-IDF + Regressão Logística. Este é o baseline do projeto: qualquer modelo
mais complexo (BERTimbau, Fase 2) precisa superá-lo para justificar o custo.

Limitação essencial: este modelo aprende ESTILO de escrita, não FATOS. Ele
erra em alegações falsas bem redigidas. A Camada 2 existe para cobrir isso.
"""

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def construir_modelo() -> Pipeline:
    """Monta o pipeline TF-IDF + Regressão Logística ainda não treinado.

    ngram_range=(1, 2) captura bigramas como "cura milagrosa", que isolados
    ("cura", "milagrosa") diriam menos.
    """
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=50_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classificador",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
        ]
    )


def treinar(textos: list[str], rotulos: list[int]) -> Pipeline:
    """Treina o modelo. Rótulo 1 = desinformação, 0 = legítima."""
    modelo = construir_modelo()
    modelo.fit(textos, rotulos)
    return modelo


def salvar(modelo: Pipeline, caminho: Path) -> None:
    """Serializa o modelo treinado em disco."""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, caminho)


def carregar(caminho: Path) -> Pipeline:
    """Carrega um modelo salvo por `salvar`."""
    return joblib.load(caminho)


def prever_risco(modelo: Pipeline, texto: str) -> float:
    """Devolve a probabilidade de o texto ser desinformação, entre 0 e 1."""
    return float(modelo.predict_proba([texto])[0][1])
```

- [ ] **Passo 4: Rodar e ver passar**

```bash
pytest tests/test_classificador.py -v
```

Esperado: **5 passed**.

!!! note "Não estranhem as probabilidades perto de 0,5"
    Com apenas 8 exemplos de treino, o modelo dos testes devolve valores como 0,57
    para um texto claramente sensacionalista e 0,42 para um sóbrio. **Isso é o
    esperado, não um defeito** — com pouquíssimo dado, o modelo tem pouca confiança e
    fica perto do meio.

    Repare que os testes verificam a **ordem** (`sensacionalista > sobrio`), não um
    valor absoluto. Testar `risco > 0.9` seria um teste frágil que quebraria a cada
    mudança. No dataset real da Task 5 as probabilidades ficam mais separadas.

- [ ] **Passo 5: Escrever o script de treino com avaliação honesta**

Criar `scripts/treina_modelo.py`:

```python
"""Treina o baseline no recorte de saúde e reporta as métricas.

Uso: python scripts/treina_modelo.py
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import prever_risco, salvar, treinar

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"


def main() -> None:
    # ATENÇÃO: ajuste os nomes das colunas conforme o dataset gerado na Task 5.
    coluna_texto = "text"
    coluna_rotulo = "label"

    df = pd.read_csv(CAMINHO_DADOS)
    print(f"Notícias: {len(df)}")
    print(df[coluna_rotulo].value_counts(), "\n")

    treino_x, teste_x, treino_y, teste_y = train_test_split(
        df[coluna_texto].astype(str).tolist(),
        df[coluna_rotulo].tolist(),
        test_size=0.2,
        random_state=42,
        stratify=df[coluna_rotulo].tolist(),
    )

    modelo = treinar(treino_x, treino_y)
    previsto = modelo.predict(teste_x)

    print("=== Relatório de classificação ===")
    print(classification_report(teste_y, previsto, target_names=["legítima", "desinformação"]))
    print("=== Matriz de confusão ===")
    print(confusion_matrix(teste_y, previsto))

    salvar(modelo, CAMINHO_MODELO)
    print(f"\nModelo salvo em {CAMINHO_MODELO}")


if __name__ == "__main__":
    main()
```

- [ ] **Passo 6: Treinar e registrar as métricas**

```bash
python scripts/treina_modelo.py
```

Copie o relatório para o [Canvas](canva.md) como resposta parcial à GQ4.

**Reporte F1 por classe, nunca acurácia isolada.** Com classes desbalanceadas, um
modelo que chuta sempre "legítima" pode ter 85% de acurácia e ser inútil — a matriz de
confusão mostra isso na hora.

- [ ] **Passo 7: Commit**

```bash
git add src/verdade_ou_fake/classificador.py tests/test_classificador.py scripts/treina_modelo.py
git commit -m "feat: classificador baseline TF-IDF + regressão logística"
```

---

## Task 7: Regras de fusão

**Frente D.** Depende só da Task 1 — pode ser feita em paralelo com tudo.

**Arquivos:**

- Criar: `src/verdade_ou_fake/fusao.py`, `tests/test_fusao.py`

**Interfaces:**

- Consome: `Alegacao`, `Evidencia`, `Veredito` de `tipos.py`
- Produz: `LIMIAR_RISCO_ALTO: float` e `fundir(risco_textual: float, alegacao: Alegacao | None, evidencia: Evidencia | None) -> Veredito`

- [ ] **Passo 1: Escrever o teste falho**

Criar `tests/test_fusao.py`:

```python
from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="ivermectina",
    medicamento_en="Ivermectin",
    condicao_pt="covid-19",
    condicao_en="COVID-19",
)
SEM_COBERTURA = Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
COBERTURA_FORTE = Evidencia(cobertura="encontrada", forca="forte", artigos=[])
COBERTURA_FRACA = Evidencia(cobertura="encontrada", forca="fraca", artigos=[])


def test_sem_alegacao_extraida_nao_verifica():
    veredito = fundir(risco_textual=0.9, alegacao=None, evidencia=None)
    assert veredito.rotulo == "Não foi possível verificar"
    assert veredito.confianca == "baixa"


def test_sem_alegacao_ainda_reporta_o_risco_textual():
    veredito = fundir(risco_textual=0.9, alegacao=None, evidencia=None)
    assert veredito.risco_textual == 0.9
    assert "sinais de alerta" in veredito.explicacao.lower()


def test_literatura_ausente_nunca_afirma_que_e_falso():
    veredito = fundir(0.9, ALEGACAO, SEM_COBERTURA)
    assert veredito.rotulo == "Não foi possível verificar"
    assert "falso" not in veredito.rotulo.lower()
    assert "não encontramos" in veredito.explicacao.lower()


def test_literatura_forte_com_texto_sobrio_e_tema_com_respaldo():
    veredito = fundir(0.2, ALEGACAO, COBERTURA_FORTE)
    assert veredito.rotulo == "Tema com respaldo na literatura"
    assert veredito.confianca == "media"


def test_literatura_forte_com_texto_sensacionalista_alerta_exagero():
    veredito = fundir(0.9, ALEGACAO, COBERTURA_FORTE)
    assert veredito.rotulo == "Existe literatura, mas o texto tem sinais de alerta"
    assert veredito.confianca == "media"


def test_literatura_fraca_e_sinalizada_como_limitada():
    veredito = fundir(0.2, ALEGACAO, COBERTURA_FRACA)
    assert veredito.rotulo == "Literatura limitada sobre o tema"
    assert veredito.confianca == "baixa"


def test_veredito_carrega_a_alegacao_e_a_evidencia():
    veredito = fundir(0.5, ALEGACAO, COBERTURA_FORTE)
    assert veredito.alegacao == ALEGACAO
    assert veredito.evidencia == COBERTURA_FORTE


def test_nenhum_veredito_afirma_verdade_absoluta():
    combinacoes = [
        fundir(0.1, ALEGACAO, COBERTURA_FORTE),
        fundir(0.9, ALEGACAO, COBERTURA_FORTE),
        fundir(0.5, ALEGACAO, COBERTURA_FRACA),
        fundir(0.5, ALEGACAO, SEM_COBERTURA),
        fundir(0.5, None, None),
    ]
    for veredito in combinacoes:
        assert "comprovado" not in veredito.rotulo.lower()
        assert "garantido" not in veredito.rotulo.lower()
```

O último teste é uma trava ética: nenhuma combinação de entradas pode produzir um
rótulo que soe como garantia. Se alguém no futuro adicionar um rótulo assim, o teste
quebra.

- [ ] **Passo 2: Rodar e ver falhar**

```bash
pytest tests/test_fusao.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.fusao'`.

- [ ] **Passo 3: Implementar**

Criar `src/verdade_ou_fake/fusao.py`:

```python
"""Etapa [3] — combina o sinal das duas camadas em um veredito.

Regras explícitas, não um modelo treinado. Duas razões: não existe dado
rotulado para supervisionar a fusão, e regras são auditáveis — o usuário
consegue ver por que recebeu aquele resultado.

Princípio inegociável: ausência de evidência NUNCA vira "é falso".
"""

from verdade_ou_fake.tipos import Alegacao, Evidencia, Veredito

LIMIAR_RISCO_ALTO = 0.6

AVISO = "Este resultado é informativo e não substitui orientação médica."


def fundir(
    risco_textual: float,
    alegacao: Alegacao | None,
    evidencia: Evidencia | None,
) -> Veredito:
    """Aplica a tabela de decisão descrita em docs/arquitetura.md."""
    risco_alto = risco_textual >= LIMIAR_RISCO_ALTO

    if alegacao is None or evidencia is None:
        complemento = (
            " O texto apresenta sinais de alerta na forma de escrita."
            if risco_alto
            else " O texto não apresenta sinais de alerta evidentes."
        )
        return Veredito(
            rotulo="Não foi possível verificar",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                "Não identificamos um par medicamento + condição clínica no texto, "
                "então não houve o que consultar na literatura científica."
                + complemento
                + " "
                + AVISO
            ),
        )

    if evidencia.cobertura == "nao_cobre":
        return Veredito(
            rotulo="Não foi possível verificar",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Não encontramos literatura no PubMed sobre {alegacao.medicamento_pt} "
                f"para {alegacao.condicao_pt}. Ausência de estudos não significa que a "
                "afirmação seja falsa — pode apenas não ter sido pesquisada ainda. "
                + AVISO
            ),
        )

    if evidencia.forca == "fraca":
        return Veredito(
            rotulo="Literatura limitada sobre o tema",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Encontramos estudos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt}, mas de tipos que oferecem evidência fraca "
                "(relatos de caso, estudos preliminares). " + AVISO
            ),
        )

    if risco_alto:
        return Veredito(
            rotulo="Existe literatura, mas o texto tem sinais de alerta",
            confianca="media",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Há estudos sobre {alegacao.medicamento_pt} e {alegacao.condicao_pt}, "
                "mas a forma como a notícia foi escrita tem características associadas "
                "a desinformação. Vale conferir as fontes originais abaixo. " + AVISO
            ),
        )

    return Veredito(
        rotulo="Tema com respaldo na literatura",
        confianca="media",
        risco_textual=risco_textual,
        alegacao=alegacao,
        evidencia=evidencia,
        explicacao=(
            f"Existem estudos de boa qualidade sobre {alegacao.medicamento_pt} e "
            f"{alegacao.condicao_pt}. Isso indica que o tema é pesquisado, não que a "
            "afirmação específica da notícia esteja correta. " + AVISO
        ),
    )
```

- [ ] **Passo 4: Rodar e ver passar**

```bash
pytest tests/test_fusao.py -v
```

Esperado: **8 passed**.

- [ ] **Passo 5: Commit**

```bash
git add src/verdade_ou_fake/fusao.py tests/test_fusao.py
git commit -m "feat: regras de fusão das duas camadas em veredito"
```

---

## Task 8: Pipeline completo

**Todos juntos** — é o momento de integração. Depende das Tasks 2, 3, 4, 6 e 7.

**Arquivos:**

- Criar: `src/verdade_ou_fake/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**

- Consome: tudo das tarefas anteriores
- Produz: `analisar_texto(texto, modelo, vocabulario, buscar) -> Veredito` e `analisar_link(url, modelo, vocabulario) -> Veredito | None`

`analisar_texto` recebe a função de busca como parâmetro — é isso que permite testá-la
sem rede, passando uma função falsa.

- [ ] **Passo 1: Escrever o teste falho**

Criar `tests/test_pipeline.py`:

```python
from pathlib import Path

from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.pipeline import analisar_texto
from verdade_ou_fake.tipos import Evidencia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "MILAGRE! Remédio secreto elimina a doença em 3 dias sem efeito colateral",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
    "Pesquisa universitária analisa o uso do medicamento em pacientes internados",
]
ROTULOS = [1, 1, 0, 0]


def modelo_de_teste():
    return treinar(TEXTOS, ROTULOS)


def busca_falsa_com_evidencia(_alegacao):
    return Evidencia(cobertura="encontrada", forca="forte", artigos=[])


def busca_falsa_sem_evidencia(_alegacao):
    return Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])


def test_texto_com_par_conhecido_produz_veredito_com_alegacao():
    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
    )
    assert veredito.alegacao is not None
    assert veredito.alegacao.medicamento_en == "Ivermectin"
    assert veredito.rotulo == "Tema com respaldo na literatura"


def test_texto_sem_par_nao_chega_a_buscar():
    chamadas = []

    def busca_espia(alegacao):
        chamadas.append(alegacao)
        return busca_falsa_com_evidencia(alegacao)

    veredito = analisar_texto(
        "Prefeitura anuncia novas obras na avenida central da cidade.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_espia,
    )
    assert chamadas == []
    assert veredito.rotulo == "Não foi possível verificar"


def test_sem_literatura_o_veredito_e_nao_verificavel():
    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_sem_evidencia,
    )
    assert veredito.rotulo == "Não foi possível verificar"


def test_veredito_sempre_traz_risco_textual_valido():
    veredito = analisar_texto(
        "Estudo sobre metformina e diabetes.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
    )
    assert 0.0 <= veredito.risco_textual <= 1.0
```

O segundo teste verifica algo importante: sem par extraído, o sistema **não chama o
PubMed**. Requisição inútil é lentidão para o usuário e carga desnecessária numa API
pública gratuita.

- [ ] **Passo 2: Rodar e ver falhar**

```bash
pytest tests/test_pipeline.py -v
```

Esperado: **FALHA** com `ModuleNotFoundError: No module named 'verdade_ou_fake.pipeline'`.

- [ ] **Passo 3: Implementar**

Criar `src/verdade_ou_fake/pipeline.py`:

```python
"""Costura as quatro etapas do sistema.

Este módulo não tem regra de negócio própria — ele só ordena as chamadas. Toda
decisão está nos módulos das etapas.
"""

from collections.abc import Callable
from pathlib import Path

from sklearn.pipeline import Pipeline as ModeloSklearn

from verdade_ou_fake.classificador import prever_risco
from verdade_ou_fake.evidencia import buscar_evidencia
from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.ingestao import extrair_noticia
from verdade_ou_fake.tipos import Alegacao, Evidencia, Veredito
from verdade_ou_fake.vocabulario import extrair_alegacao

BuscadorDeEvidencia = Callable[[Alegacao], Evidencia]


def analisar_texto(
    texto: str,
    modelo: ModeloSklearn,
    vocabulario: dict[str, list[tuple[str, str]]],
    buscar: BuscadorDeEvidencia = buscar_evidencia,
) -> Veredito:
    """Roda as etapas [1], [2] e [3] sobre um texto já extraído.

    `buscar` é injetável para que os testes rodem sem tocar a rede.
    """
    risco = prever_risco(modelo, texto)
    alegacao = extrair_alegacao(texto, vocabulario)

    # Sem o par medicamento+condição não há query a fazer — pular a busca
    # evita requisição inútil a uma API pública gratuita.
    evidencia = buscar(alegacao) if alegacao is not None else None

    return fundir(risco_textual=risco, alegacao=alegacao, evidencia=evidencia)


def analisar_link(
    url: str,
    modelo: ModeloSklearn,
    vocabulario: dict[str, list[tuple[str, str]]],
) -> Veredito | None:
    """Fluxo completo, da etapa [0] à [3]. Devolve None se a extração falhar."""
    noticia = extrair_noticia(url)
    if noticia is None:
        return None

    texto_completo = f"{noticia.titulo}\n\n{noticia.texto}"
    return analisar_texto(texto_completo, modelo, vocabulario)
```

- [ ] **Passo 4: Rodar e ver passar**

```bash
pytest tests/test_pipeline.py -v
```

Esperado: **4 passed**.

- [ ] **Passo 5: Rodar a suíte inteira**

```bash
pytest -v
```

Esperado: **50 passed** — 5 de tipos, 4 de ingestão, 7 de vocabulário, 12 de evidência,
5 de dataset, 5 de classificador, 8 de fusão e 4 de pipeline. Este é o marco: o
pipeline está integrado.

- [ ] **Passo 6: Commit**

```bash
git add src/verdade_ou_fake/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline integrando as quatro etapas"
```

---

## Task 9: Interface Streamlit

**Frente D.** Depende da Task 8.

**Arquivos:**

- Criar: `app.py`
- Modificar: `README.md` (seção de como rodar)

**Interfaces:**

- Consome: `analisar_link`, `carregar` (modelo), `carregar_vocabulario`

Esta tarefa não tem teste automatizado — é interface. A verificação é manual e está
descrita no Passo 3.

- [ ] **Passo 1: Implementar a interface**

Criar `app.py` na raiz do projeto:

```python
"""Interface web do Verdade ou Fake.

Uso: streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import carregar
from verdade_ou_fake.pipeline import analisar_link
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"
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

modelo, vocabulario = carregar_recursos()

url = st.text_input(
    "Cole o link da notícia",
    placeholder="https://portal.exemplo.com/saude/materia",
)

if st.button("Analisar", type="primary") and url:
    with st.spinner("Extraindo o texto e consultando a literatura científica..."):
        veredito = analisar_link(url, modelo, vocabulario)

    if veredito is None:
        st.error(
            "Não conseguimos extrair o texto dessa página. Ela pode estar atrás de "
            "paywall, exigir login, ou usar um formato que ainda não suportamos."
        )
    else:
        st.subheader(f"{CORES[veredito.confianca]} {veredito.rotulo}")
        st.write(veredito.explicacao)

        col_a, col_b = st.columns(2)
        col_a.metric("Risco pelo texto", f"{veredito.risco_textual:.0%}")
        col_b.metric("Confiança do veredito", veredito.confianca.capitalize())

        if veredito.alegacao:
            st.info(
                f"**Alegação identificada:** {veredito.alegacao.medicamento_pt} "
                f"→ {veredito.alegacao.condicao_pt}"
            )

        if veredito.evidencia and veredito.evidencia.artigos:
            st.subheader("Fontes científicas encontradas")
            for artigo in veredito.evidencia.artigos:
                tipos = ", ".join(artigo.tipos_estudo) or "não classificado"
                st.markdown(
                    f"- [{artigo.titulo}](https://pubmed.ncbi.nlm.nih.gov/{artigo.pmid}/)  \n"
                    f"  <sub>{tipos} · {artigo.ano or 's/d'} · PMID {artigo.pmid}</sub>",
                    unsafe_allow_html=True,
                )

        with st.expander("Como interpretar este resultado"):
            st.markdown(
                """
                O sistema tem **duas camadas** e nenhuma delas dá veredito médico:

                - **Risco pelo texto** vem de um modelo que aprendeu padrões de
                  escrita típicos de desinformação. Ele avalia *como* a notícia foi
                  escrita, não se o que ela afirma é verdade.
                - **Fontes científicas** vêm de uma busca no PubMed pelo par
                  medicamento + condição encontrado no texto.

                Quando não encontramos literatura, respondemos *"não foi possível
                verificar"* — nunca *"é falso"*. Ausência de estudos não é prova de
                ineficácia.
                """
            )
```

- [ ] **Passo 2: Rodar a interface**

```bash
streamlit run app.py
```

Abre em `http://localhost:8501`.

- [ ] **Passo 3: Verificação manual**

Testar os quatro caminhos e anotar o resultado de cada um:

| Cenário | Link a usar | Esperado |
|---|---|---|
| Notícia de saúde com par conhecido | matéria sobre um medicamento do vocabulário | Veredito com alegação e fontes |
| Notícia sem termo de saúde | matéria de política ou esporte | "Não foi possível verificar" |
| Par sem literatura | medicamento + condição sem estudos | "Não foi possível verificar", nunca "é falso" |
| Link inválido ou com paywall | qualquer URL quebrada | Mensagem de erro amigável, sem stack trace |

- [ ] **Passo 4: Documentar como rodar**

Acrescentar ao `README.md`, logo antes da seção "Fontes de dados":

````markdown
## Como rodar

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python scripts/prepara_dataset.py    # gera o recorte de saúde
python scripts/treina_modelo.py      # treina e salva o baseline
streamlit run app.py                 # abre a interface

pytest                               # roda os testes
```
````

- [ ] **Passo 5: Commit**

```bash
git add app.py README.md
git commit -m "feat: interface Streamlit para análise de links"
```

---

## Definição de pronto (Fase 1)

A PoC está concluída quando:

- [ ] `pytest` passa inteiro, sem nenhum teste tocando a rede
- [ ] `streamlit run app.py` recebe um link real e devolve veredito com fontes
- [ ] A taxa de extração da Task 2 está registrada no Canvas (GQ8)
- [ ] O relatório de classificação da Task 6 está registrado no Canvas (GQ4)
- [ ] O `dados/README.md` está preenchido com os números reais
- [ ] Os quatro cenários da Task 9 foram testados manualmente

## O que vem na Fase 2

Fora do escopo deste plano, registrado para não se perder:

- Fine-tuning do BERTimbau, comparado contra o baseline
- NLI para distinguir **apoia** de **contradiz** na Camada 2c
- Ampliação do vocabulário com o DeCS completo (decisão D1)
- Onda 2 de coleta de dados nas agências de checagem
- Separação em API FastAPI
- Avaliação em portais fora do conjunto de treino, para medir viés de fonte
