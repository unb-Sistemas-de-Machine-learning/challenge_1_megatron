# ADR 0003 — Embeddings multilíngues locais em ONNX

## Contexto

A alegação chega em português e a literatura está em inglês. A recuperação precisa
aproximar os dois idiomas. A hospedagem é uma CPU gratuita, e a imagem precisa ser
pequena e subir rápido.

## Decisão

Usar `paraphrase-multilingual-MiniLM-L12-v2`, modelo multilíngue que coloca português e
inglês no mesmo espaço vetorial, executado por ONNX na biblioteca `fastembed` (sem
PyTorch). O modelo é configurável por `VOF_MODELO_EMBEDDING`. Os vetores são
normalizados, então o produto interno é o cosseno.

## Alternativas consideradas

- **API de embeddings de terceiros.** Mais uma cota e mais uma chamada de rede a cada
  consulta, além de enviar o texto do usuário a outro serviço.
- **Traduzir a consulta para inglês e usar um modelo só em inglês.** Acrescenta uma
  etapa que pode errar e que gastaria cota de LLM. O modelo multilíngue dispensa a
  tradução na recuperação.
- **O mesmo modelo via PyTorch (`sentence-transformers`).** Funciona, mas a imagem de
  runtime carregaria o PyTorch inteiro sem ganho para o usuário.

## Consequências

- Imagem de runtime sem PyTorch.
- Nenhum texto do usuário sai do servidor na etapa de recuperação.
- Modelo pequeno e genérico, não treinado para texto biomédico. Pode confundir fármacos
  de nome parecido, uma das razões da busca híbrida com BM25.
- Trocar de modelo exige reconstruir o banco (`scripts/constroi_base.py`), porque os
  vetores guardados são do modelo antigo.
