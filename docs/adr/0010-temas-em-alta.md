# 0010 Temas em alta: planilha da equipe e Google Notícias alimentando a base

## Contexto

A página inicial só oferecia quatro exemplos fixos, e a base de conhecimento só crescia
quando alguém perguntava algo fora dela. Queríamos mostrar o que está circulando sobre
saúde na semana e, ao mesmo tempo, preparar a base para essas perguntas antes de elas
chegarem.

## Decisão

Uma rotina periódica (a cada 6 horas, e sob demanda por
`scripts/atualiza_destaques.py`) monta a lista de temas em alta a partir de duas fontes:

- **Planilha da equipe.** Um Google Sheets publicado como CSV (`VOF_PLANILHA_CSV`), com
  uma alegação por linha. É a curadoria humana e tem prioridade.
- **Google Notícias.** As manchetes de saúde do dia, das quais um LLM extrai alegações
  com intervenção e doença nomeadas. Preenche as vagas que a planilha deixar.

Para cada tema, a rotina busca estudos no PubMed e os indexa na base (origem
`destaque`), roda a checagem completa, que fica no cache, e busca até três notícias
recentes sobre o assunto para mostrar no cartão.

Duas regras de qualidade:

- **O texto das notícias não entra na base.** A base guarda só evidência científica. A
  notícia é o que o sistema checa, não a fonte da checagem.
- **Tema automático só aparece com veredito afirmativo de confiança alta.** No primeiro
  teste, três de quatro temas tirados de manchetes eram vagos ("tratamento no ES previne
  amputações") e geraram vereditos ruins, como vacina contra meningite marcada como
  inconclusiva. Temas da planilha aparecem sempre, porque alguém os escolheu.

## Alternativas consideradas

- **API do Google Sheets com conta de serviço.** Permitiria escrever na planilha, mas
  exige credenciais. Ler um CSV publicado não exige nenhuma.
- **API de busca do Google.** Exige chave e tem cota diária. O RSS do Google Notícias
  entrega manchetes e busca por tema sem credencial.
- **Temas mais consultados no próprio banco.** Mostra o que os usuários perguntam, mas
  expõe texto digitado por terceiros sem curadoria.
- **Indexar as notícias na base.** Aumentaria a cobertura, ao custo de o sistema citar
  notícia como se fosse evidência.

## Consequências

- A base cresce todos os dias com estudos sobre o que está em pauta, e as perguntas
  sobre esses temas respondem do cache.
- Cada atualização gasta cota do LLM: uma chamada para ler as manchetes e duas por tema.
  O máximo é de 6 temas por rodada, com pausa entre eles.
- A planilha publicada é pública e somente leitura. Quem edita a planilha muda a página
  inicial sem deploy, então o acesso de edição deve ficar restrito à equipe.
- O feed RSS do Google Notícias declara uso pessoal e não comercial. O uso aqui é
  acadêmico e de baixo volume, mas isso precisa ser revisto antes de qualquer uso fora
  da disciplina.
- A seção pode ficar vazia: sem planilha, e num dia em que nenhuma manchete passe pelo
  filtro, ela não aparece.
