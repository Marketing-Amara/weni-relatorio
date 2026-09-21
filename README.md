# Relatório Weni — automação fora do Excel

Este repositório busca, todo dia de manhã (automaticamente, via GitHub Actions),
os contatos que pediram para falar com vendedor/atendente/humano/comercial na
Weni, filtra pelos que têm Hunter = "digital", e gera `output/relatorio.xlsx`.

É a mesma lógica que estava na consulta do Power Query, só que rodando fora do
Excel — então não trava a planilha esperando a API responder, e só busca o que
é novo a cada execução (guarda um cache de mensagens e contatos já buscados).

## Configuração (fazer uma vez só)

1. **Crie um repositório novo no GitHub** (recomendo deixar **privado**, já
   que o relatório final vai conter nomes e mensagens de contatos reais).
2. **Suba estes arquivos** para o repositório (pelo site do GitHub, arrastando
   os arquivos em "Add file → Upload files", ou via `git push` se você usa
   linha de comando).
3. **Cadastre o token da API como Secret:**
   - No repositório, vá em **Settings → Secrets and variables → Actions**.
   - Clique em **New repository secret**.
   - Nome: `WENI_API_TOKEN`
   - Valor: o token real da API do Weni (o mesmo que estava no lugar de
     `"TOKEN"` na consulta do Power Query).
   - Salve. Esse token nunca fica escrito em nenhum arquivo do repositório.
4. **Teste rodando manualmente:** vá na aba **Actions** do repositório,
   clique no workflow "Relatório Weni" e depois em **Run workflow**. A
   primeira execução demora mais (busca a base de contatos inteira, do jeito
   que ela é hoje); as próximas são bem mais rápidas, porque só buscam o que
   mudou.
5. Depois disso, o relatório roda sozinho todo dia às 07:00 (horário de
   Brasília) e o arquivo `output/relatorio.xlsx` fica sempre atualizado
   dentro do repositório — é só abrir/baixar ele quando precisar.

## Ajustar o que a consulta busca

Tudo isso está no topo do arquivo `scripts/gerar_relatorio.py`:

- `DATA_INICIO` — data a partir da qual as mensagens são consideradas
  (hoje: 14 de junho de 2026).
- `PALAVRAS_ALVO` — palavras que, junto com "falar com", marcam um pedido de
  atendimento (hoje: vendedor, atendente, humano, comercial).
- `VALOR_HUNTER_ALVO` — valor do campo Hunter usado no filtro final (hoje:
  "digital").

Para mudar o horário em que roda todo dia, edite a linha `cron:` no arquivo
`.github/workflows/relatorio.yml` (o horário do cron é sempre em UTC — o
valor atual, `0 10 * * *`, corresponde a 07:00 em Brasília).

## Por que os dados brutos não ficam salvos no repositório

O arquivo `.gitignore` impede que `data/messages_cache.json` e
`data/contacts_cache.json` sejam commitados — eles contêm dados de contatos
(nome, telefone/URN, mensagens) e não é uma boa prática deixar isso
acumulando para sempre no histórico do git. Esses arquivos ficam guardados
apenas no cache do GitHub Actions entre uma execução e outra. Só o relatório
final (`output/relatorio.xlsx`), que é o que você já usa hoje no Excel,
fica salvo no repositório.
