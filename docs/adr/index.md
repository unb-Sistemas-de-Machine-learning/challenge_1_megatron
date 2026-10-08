# Decisões de arquitetura (ADRs)

Cada arquivo registra uma decisão: contexto, decisão, alternativas consideradas e
consequências. O formato é curto de propósito.

| # | Decisão | Status |
|---|---|---|
| [0001](0001-rag-com-llm-de-terceiros.md) | Trocar o pipeline de classificador + NLI por RAG com LLM de terceiros | Aceita |
| [0002](0002-sqlite-busca-vetorial-exata.md) | SQLite com busca vetorial exata em memória | Aceita |
| [0003](0003-embeddings-multilingues-onnx.md) | Embeddings multilíngues locais em ONNX | Aceita |
| [0004](0004-cliente-openai-compativel-groq.md) | Cliente compatível com OpenAI, Groq como padrão, com fallback entre modelos | Aceita |
| [0005](0005-fastapi-sse-front-estatico.md) | FastAPI com SSE e front estático em vez de Streamlit | Aceita |
| [0006](0006-base-em-lote-com-busca-ao-vivo.md) | Base pré-ingerida em lote com ampliação ao vivo sob demanda | Aceita |
| [0007](0007-guardas-deterministicas.md) | Guardas determinísticas sobre a saída do LLM | Aceita |
| [0008 Hospedagem: de Hugging Face Spaces para VM no Azure](0008-hospedagem.md) | VM no Azure com o crédito de estudante, depois que o Space gratuito deixou de existir | Revista em 07/10/2026 |
| [0009](0009-bertimbau-sinal-secundario.md) | BERTimbau como sinal secundário opcional | Aceita |

Visão de conjunto em [Arquitetura](../arquitetura.md).
