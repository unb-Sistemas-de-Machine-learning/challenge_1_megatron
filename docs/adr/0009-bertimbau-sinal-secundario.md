# ADR 0009 — Manter o BERTimbau como sinal secundário opcional

## Contexto

O BERTimbau foi treinado pelo grupo no recorte de saúde do Fake.br. Seu model card
(`modelos/cards/bertimbau.json`) registra F1 macro same-source de 0,957 num teste de 70
notícias, e há um gate de promoção para produção. Mas o classificador mede estilo de
portal, não fato, e o corpus é de 2016 a 2018, quase sem saúde. Como decisor do
veredito, não serviu. Como indicador do estilo do texto, ainda tem alguma utilidade para
o leitor.

## Decisão

Manter o modelo como **sinal de estilo do texto**, exibido à parte e rotulado como tal.
`sinal_estilo.py` só o carrega se PyTorch e os pesos estiverem disponíveis (e, desde a
revisão abaixo, só com `VOF_SINAL_ESTILO=1`);
`modelo_producao.py` continua exigindo o card em `producao` e o hash dos pesos
conferindo. O sinal roda em paralelo à identificação da alegação, com prazo de 4
segundos: se não chega, a resposta segue sem ele. Ele não participa do veredito nem da
confiança.

## Alternativas consideradas

- **Remover.** Joga fora trabalho e um bom exemplo de gate de qualidade e model card, e
  deixa o repositório sem nenhum modelo treinado pelo grupo.
- **Manter como decisor.** É o desenho que falhou.
- **Combinar com o RAG por regras.** Voltaria a misturar um proxy de estilo com um
  veredito de conteúdo, sem dado rotulado para calibrar a mistura.

## Consequências

- O runtime leve (`requirements.txt`) não instala PyTorch. O sinal só aparece onde
  PyTorch e os pesos estão disponíveis (por exemplo, com `requirements-treino.txt`).
  `GET /api/saude` informa se está ativo (campo `sinal_estilo`).
- Preservamos o registro do processo: baseline, BERTimbau, card, gate.
- Risco de o leitor dar peso demais ao indicador. A interface o apresenta como sinal de
  estilo, e a documentação diz que ele não mede veracidade.

## Revisão em 07/10/2026

No teste com um link real, o classificador deu 99,8% de risco ao verbete da Wikipédia
sobre ivermectina, um texto legítimo. Mostrar esse número ao lado do veredito enganaria
o usuário. O sinal passou a ficar **desligado por padrão** e só é carregado com
`VOF_SINAL_ESTILO=1`. O modelo, o card e o gate continuam no repositório como registro
do trabalho de treino e avaliação.
