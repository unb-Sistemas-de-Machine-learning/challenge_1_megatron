# ADR 0002 — SQLite com busca vetorial exata em memória

## Contexto

A base de conhecimento tem 1.069 resumos na versão atual e cresce com a ingestão
semanal e a busca ao vivo. Precisamos também registrar cada consulta, guardar o cache
de páginas e servir busca lexical.

## Decisão

Um único arquivo SQLite (`banco.py`) com três papéis: base de conhecimento (tabela
`documentos` e índice FTS5 para BM25), registro de consultas com feedback (`consultas`)
e cache de páginas (`paginas`). Os embeddings ficam num BLOB por documento. Na primeira
busca, o `Recuperador` carrega todos numa matriz numpy e calcula o cosseno exato contra
a consulta. A matriz é recarregada quando o total de documentos muda.

## Alternativas consideradas

- **pgvector em Postgres gerenciado.** Boa opção para escala, mas acrescenta um serviço
  externo, credenciais e rede entre o app e o banco, para uma base de milhares de
  documentos.
- **Chroma.** Fácil de embutir, mas é mais uma dependência e um formato de
  armazenamento próprio. Ainda precisaríamos de SQLite para o registro de consultas e o
  cache.
- **Qdrant.** Servidor dedicado. Mesmo argumento do pgvector.
- **FAISS.** Índice em memória pensado para milhões de vetores. Na nossa escala a busca
  exata em numpy basta (a busca híbrida inteira leva cerca de 10 ms, medido), e o FAISS
  não resolve persistência nem busca lexical.

## Consequências

- Nenhum servidor de banco para subir ou pagar. Backup é copiar um arquivo.
- Busca exata: sem aproximação e sem ajuste de índice.
- Processo único: a conexão é compartilhada com uma trava, e várias réplicas não
  compartilhariam o arquivo.
- A matriz inteira fica na memória. Serve para milhares de documentos e passa a pesar
  bem antes de milhões. Nesse ponto, migrar para pgvector é a saída natural, e o
  `Recuperador` é a parte a trocar.
- No Space gratuito o disco não é persistente (ver [ADR 0008](0008-hugging-face-spaces.md)):
  a base é reconstruída na imagem e o registro de consultas zera a cada reinício.
