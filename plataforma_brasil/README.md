# Observatório Brasil — mundos real e virtual

Aplicação local em **Python 3.10+ e SQLite**, com interface web e catálogo integrado ao pacote original. Não exige `pip install`.

## Abrir

Nesta pasta:

```bash
python3 app.py serve
```

Acesse **http://127.0.0.1:8765**. Para outra porta: `python3 app.py serve --port 8766`.

Também é possível executar `./iniciar.sh`. O servidor escuta apenas no computador local. O banco é inicializado automaticamente.

## Funcionalidades

- Dois ambientes: **Mundo real** e **Mundo virtual**, com registros compartilhados quando a fonte documenta a relação.
- Todos os **34 indicadores, 12 cruzamentos e 18 perguntas**, com definições e fontes relacionadas.
- **59 fontes** com recorte Brasil, situação de acesso, coletor, recursos descobertos e histórico de execução.
- Mapa do Brasil com malha de UFs e limites dos municípios com dados coletados pelo IBGE, filtros por UF/município, período, natureza e camada temática.
- Consulta de estatísticas, documentos, acontecimentos documentados e contexto, com exportação CSV.
- Fichas com origem, unidade, precisão geográfica, data, indicadores e metadados.
- Importação municipal do Disque 100 com validação IBGE, deduplicação na célula e auditoria de exclusões.
- Importação JSON de informações documentadas, inclusive publicações internacionais sobre o Brasil.
- Ligação para o painel original, com suas tabelas e análises anteriores.

O mapa usa Leaflet 1.9.4 via CDN. O mapa-base padrão usa os **limites IBGE já coletados**, sem solicitar imagens ao OpenStreetMap. Em **Mapa-base → Ruas · OpenStreetMap**, é possível habilitar as imagens externas. A configuração envia a origem HTTP exigida pelo serviço (`Referrer-Policy: strict-origin-when-cross-origin`) e mostra um aviso se as imagens falharem. A biblioteca via CDN exige internet; se ela não carregar, as consultas, catálogos e fichas continuam disponíveis.

## Todas as fontes no mapa

A seção **Fontes, temas e cobertura**, dentro do explorador, integra as 59 entradas do catálogo. O filtro **Fonte** permite consultar as observações e publicações de uma instituição. A busca localiza instituições e assuntos, e o filtro de cobertura distingue dados territoriais, conteúdo nacional, fontes sem observações importadas e referências fora do recorte Brasil.

Cada ficha mostra acesso, limitações, indicadores, temas, última consulta e recursos encontrados. As fontes sem observações geográficas não recebem coordenadas artificiais.

O **Dossiê territorial** separa os registros estritamente localizados no município/UF das informações nacionais relacionadas. Um documento nacional continua nacional ao selecionar uma cidade. As camadas temáticas também incluem registros ligados aos indicadores daquela dimensão, além do tema principal de cada registro.

Após a ampliação documental, a base contém **34 registros de 12 fontes**: 22 observações estatísticas, 9 documentos e 3 registros de contexto técnico. As 59 fontes foram avaliadas: 11 tiveram trechos importados nesta rotina, 19 não apresentaram trecho elegível, 6 ficaram fora do recorte, 14 dependem de acesso condicionado e 9 retornaram falhas HTTP. A fonte Disque 100 mantém seus agregados municipais mesmo quando sua página inicial não oferece um parágrafo documental elegível.

Esses números descrevem a execução realizada, não uma garantia de disponibilidade futura das páginas. Os resultados exatos e as mensagens por fonte ficam no histórico.

## Coleta

```bash
python3 app.py collect
python3 app.py collect --source A11
python3 app.py collect --source A22
python3 app.py collect-catalogo
python3 app.py collect-catalogo --source A01,A13 --workers 2 --max-mb 4
```

| Fonte | Implementação atual |
|---|---|
| A11 — IBGE | Localidades, malha de UFs e limites dos municípios presentes nos registros; não são ocorrências. |
| A22 — SaferNet | Extração das contagens de denúncias online de 2023 e 2024 e registro da publicação institucional. |
| A01 — MJSP | Descoberta de relatórios e painel; não extrai automaticamente números de PDFs/Power BI. |
| A02 — Disque 100 | Descoberta, download limitado/retomável, perfil do CSV e importação municipal por mapeamento. |
| A03 — SmartLab | Descoberta de arquivos na página; uma página dinâmica pode não revelar arquivos. |
| A04 — MTE | Descoberta de documentos disponíveis no HTML. |
| Outras entradas | Catálogo e condição de acesso. Coletores específicos ainda não implementados. |

`collect` não inicia automaticamente downloads de centenas de MB do Disque 100. O usuário escolhe o recurso e seu limite. `--max-mb` controla o limite dos coletores de HTML/JSON (padrão: 40 MB).

Os downloads HTML/JSON geram snapshots SHA256 em `var/snapshots/`. Recursos descobertos **não são dados extraídos**. Erros não são convertidos em sucesso nem substituem uma versão anterior válida. Atualize a página depois de uma coleta/importação.

`collect-catalogo` verifica páginas públicas de todas as entradas elegíveis. Extrai parágrafos com referência explícita ao Brasil nas fontes internacionais e texto substantivo das páginas brasileiras. Menus, rodapés e mensagens de navegação não sustentam a relação com o país. APIs, documentação técnica e instruções de acesso são apresentadas como contexto, não como casos ou séries. Não infere contagens, datas de ocorrência nem municípios a partir de trechos de texto. PDFs públicos podem ser lidos quando o utilitário opcional `pdftotext` estiver instalado. A execução é limitada a 1–8 workers e não consulta serviços autenticados sem as respectivas integrações.

### Disque 100: baixar e examinar

Na aba **Fontes e coleta**, consulte os recursos A02. Alguns endereços sem extensão retornam diretamente um CSV.

```bash
python3 app.py download --url "URL_OFICIAL_DO_CSV" --max-mb 1200
python3 app.py profile-disque "var/downloads/ARQUIVO.csv"
```

O download informa o caminho e o checksum. Interrupções de rede preservam um arquivo `.part`; a execução seguinte tenta retomar se o servidor confirmar o intervalo. Quando o limite configurado é excedido, o parcial é descartado. Se a fonte tiver atualizado o arquivo entre tentativas, remova o parcial e baixe novamente. Nenhum arquivo parcial é importado automaticamente.

O perfil lista apenas colunas e contagens das categorias de tráfico de pessoas, sem imprimir os registros individuais.

### Disque 100: mapear e importar

Copie `exemplos/mapeamento_disque.json` e ajuste **a partir do cabeçalho, perfil e documentação daquele recurso**. O esquema muda entre períodos.

```bash
python3 app.py import-disque "var/downloads/ARQUIVO.csv" \
  --mapping "exemplos/mapeamento_disque.json" \
  --url "URL_OFICIAL_DO_CSV"
```

Opções adicionais: `--encoding cp1252` e `--delimiter ";"`.

Regras:

1. As categorias em `valores_violacao` têm correspondência exata, desconsiderando caixa e acentos.
2. O identificador é deduplicado por **município + ano + recurso/período**, não como total global de vítimas.
3. Município deve corresponder a código IBGE ou a nome e UF exatos após normalização de acentos. O formato `3550308 | SÃO PAULO` é aceito.
4. Datas inválidas, identificadores vazios e municípios não resolvidos são excluídos e contabilizados na auditoria.
5. Células ausentes não são preenchidas com zero. Períodos parciais permanecem explicitamente parciais.
6. Reimportar a mesma URL substitui suas células atomicamente. URLs distintas não são somadas: podem ter períodos sobrepostos.
7. O campo `hash` de uma base administrativa **não é presumido como protocolo de denúncia**. Use unidade de registros administrativos enquanto sua semântica não estiver estabelecida.
8. Data de cadastro não é automaticamente data do acontecimento. O significado fica nos metadados.
9. Sem evidência do canal utilizado, os agregados entram no ambiente real como referência territorial, sem inferir recrutamento digital.

O importador publica apenas agregados e metadados de processamento; não copia os identificadores individuais para a API.

Depois de revisar um mapeamento, é possível automatizar download e importação juntos:

```bash
python3 app.py collect-disque \
  --url "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque100-terceiro-trimestre-2026" \
  --mapping exemplos/mapeamento_disque.json --max-mb 1200
python3 app.py collect --source A11
```

O segundo comando coleta os limites dos municípios que passaram a ter registros. Para novos períodos, revise o esquema antes de usar o mesmo mapeamento. O exemplo foi verificado contra o CSV de 2026-T3.

### Base já coletada nesta implementação

- **Disque 100, 2026-T3:** 1.378.060 linhas examinadas; 56 linhas nas duas categorias explícitas de tráfico de pessoas; 6 excluídas por data, identificador ou localização não resolvidos; 6 repetições de identificador dentro da célula. Resultado: **20 células municipais**, com unidade de registros administrativos distintos, não vítimas.
- SHA256 do CSV: `427993657178fd1f24aaf1c29ee975fc300ad16a02e64ff0b227454e42612141`.
- **SaferNet:** duas observações de denúncias recebidas (2023 e 2024) e uma publicação institucional de 2025.
- **IBGE:** 5.571 localidades, malha de UFs e limites dos 20 municípios com dados nesta importação.
- Total inicial: **23 registros consultáveis**, provenientes de duas fontes de conteúdo; o IBGE fornece a referência geográfica.

O CSV oficial ocupa aproximadamente 940 MB em `var/downloads/`. Os valores de 2026-T3 são de um trimestre, não de um ano completo.

## Registros documentados e fontes internacionais

### Ofertas e recrutamento no Mundo virtual

Na aba **Mundo virtual**, a seção **Ofertas e recrutamento digital** mostra fichas com filtro por classificação, recorte, ano de publicação, fonte, plataforma e texto. Ela separa `trafico_documentado`, `suspeita_nao_confirmada`, `golpe_sem_vinculo_trafico` e `alerta_geral`. Alertas gerais não são contados como ofertas individuais. País é o contexto declarado, não coordenada nem local de uma vítima. Essas fichas têm armazenamento próprio e não alteram estatísticas ou registros no mapa.

A seção **Perfil, localização e modalidades** inclui a caracterização qualitativa da SaferNet, perfil nacional da tabela 3 e modalidades da tabela 5 do relatório nacional, além das células municipais do Disque 100. O mapa contextual opcional pinta os limites municipais em laranja para um único período; clique para ver a ficha e a fonte. Perfil nacional, inquéritos e localidades não informam canal digital nem estão ligados entre si; não são apresentados como correlação ou mapa de risco. As referências sobre modalidades online incluem exploração sexual e doméstica descritas pela SaferNet e o relatório exploratório internacional da OSCE sobre coação para fraudes digitais, identificado separadamente sem vínculo brasileiro presumido. A data é a do registro administrativo, não necessariamente da ocorrência. Consulta: `/api/analise-digital`.

A seção também apresenta a linha **Oferta de trabalho** da tabela 10 (motivações para migrar) dos relatórios NETP/PAAHM. São importadas apenas linhas com todas as seis células explicitamente preenchidas e soma compatível com o total; formatos parciais permanecem pendentes, sem converter vazios em zero. Os filtros distinguem ano, UF da unidade informante e finalidade. A oferta como motivo de migração não é necessariamente falsa, digital nem meio de aliciamento. As unidades podem atender às mesmas pessoas; totais não devem ser somados às finalidades ou entre unidades. A página e o trecho constam em cada ficha.

Os perfis institucionais de **2024 e 2025** estão na mesma seção, separados por Disque 100 e SUS. São transcrições de trechos textuais da página 20 do relatório de 2024 e da página 23 do relatório de 2025. Para renovar: `python3 app.py collect-perfil-recente`. O comando baixa os dois PDFs vinculados na página oficial do MJSP, confirma os trechos e totais e substitui as fichas somente após validar os dois. Armazena os snapshots, as páginas e SHA256. Dados do SUS são preliminares: o relatório de 2024 informa 304, enquanto o de 2025 registra 340 para o mesmo ano; preservar as versões, sem supor equivalência. O Disque 100 não é diretamente comparável à série anterior combinada com Ligue 180, que foi separado. Os dois grupos também não podem ser somados entre instituições. Em 2026 há dados parciais municipais, mas não foi importado perfil nacional equivalente.

Uma correção no extrator removeu o rótulo indevido “Outras nacionalidades” das linhas da tabela 2 dos CREAS. Ele decorria de uma continuação da tabela 1 presente na mesma página; os dados da tabela 2 têm recorte nacional, sem nacionalidade informada.

```bash
python3 app.py import-recrutamento exemplos/recrutamento_fontes_publicas.json
```

O exemplo documenta um alerta geral da SaferNet sobre falsas agências de modelos nas redes sociais; a publicação não apresenta uma vaga identificável. Para novas fichas, use o mesmo formato JSON: `id` estável, título, descrição, classificação, recorte (`brasil`, `conexao_brasil` ou `internacional`), país, nome e URL da fonte, trecho de evidência e limitações são obrigatórios. Para os dois recortes ligados ao Brasil, informe `relacao_brasil`. São opcionais a plataforma, a data de publicação ISO (`AAAA-MM-DD`), a lista de sinais e o ID de fonte já catalogada. Referências internacionais sem relação com o Brasil ficam separadas por recorte.

A importação valida o lote antes de gravar, atualiza pelo ID e recusa reaproveitamento de ID para outra fonte. A classificação é atribuída por quem importa, com base no texto citado; a aplicação não verifica automaticamente a notícia nem considera phishing ou sinais isolados prova de tráfico. O sistema não coleta contas privadas, nem fornece uma lista completa de todas as ofertas. A API pública local é `/api/recrutamento`, com filtros `classificacao`, `recorte`, `ano`, `fonte_id`, `plataforma` e `q`.

```bash
python3 app.py import-registros "MEUS_REGISTROS.json"
```

O arquivo deve ser uma lista de objetos. Cada objeto exige:

```json
{
  "id": "identificador-estavel-da-fonte",
  "fonte_id": "A01",
  "recurso_url": "https://www.gov.br/URL-DO-DOCUMENTO",
  "titulo": "Título fiel ao documento",
  "descricao": "Descrição sustentada pela fonte",
  "ambiente": "real",
  "tipo": "documento",
  "tema": "Exploração e coerção",
  "ano": 2024,
  "precisao": "pais",
  "origem_publicacao": "Brasil",
  "relacao_brasil": "Explicação da relação documentada com o Brasil",
  "indicadores": [],
  "metadados": {
    "trecho_fonte": "Transcrição ou referência precisa que sustenta o registro"
  }
}
```

Esse exemplo é estrutural: não contém um acontecimento real e não deve ser importado como informação factual.

- `fonte_id` deve existir no catálogo.
- `tipo`: `documento`, `estatistica`, `acontecimento` ou `contexto`.
- `ambiente`: `real`, `virtual` ou `ambos`.
- `precisao`: `pais`, `uf`, `municipio`, `local_exato` ou `nao_informada`.
- Estatísticas exigem `valor` e `unidade`.
- Precisão municipal exige código IBGE validado e UF correspondente.
- Pontos exigem `precisao: "local_exato"`, latitude e longitude documentadas.
- Fontes internacionais exigem o país em `origem_publicacao`, a relação com o Brasil e `metadados.trecho_relacao_brasil`. Aparecem com selo próprio.
- Um mesmo `id` reaparece como uma atualização, não como uma nova contagem em cada ambiente.

As importações são operações editoriais locais; o aplicativo não confirma automaticamente o conteúdo de um documento nem converte sua publicação em confirmação judicial de crime.

## Enriquecimento de campos e documentos vinculados

```bash
python3 app.py enrich --source A01,A04,A21,A22 --limit 24 --workers 4 --max-mb 20
python3 app.py enrich --cached-only
```

O primeiro comando reprocessa os registros existentes, seleciona PDFs ainda não examinados e registra a investigação de cada URL. O segundo usa apenas os snapshots locais, sem novos downloads.

- Datas de publicação e atualização são extraídas dos metadados e dos cabeçalhos visíveis, incluindo o formato usado pelo gov.br. A data de impressão de um formulário não é tratada automaticamente como publicação.
- O período de referência é mantido separado da data editorial. Um relatório de 2021–2023 não é reduzido a um único ano. O filtro anual também encontra os anos incluídos no intervalo.
- Links do MJSP que migraram do diretório `nucleos-...` para `rede-de-nucleos-...` são recuperados somente após confirmar a resposta HTTP e o conteúdo. As URLs original e resolvida ficam nos metadados.
- Relatórios da rede NETP/PAAHM têm identificação da unidade, exercício, página e trecho de evidência quando extraídos. A localização da **unidade informante** é explicitamente distinta do local de aliciamento/exploração. Formulários com alternativas de estados não são presumidos como uma seleção válida.
- A seção 1 permite extrair células explicitamente preenchidas de vítimas atendidas, com modalidade e total separados. O total não deve ser somado aos componentes nem interpretado como total deduplicado entre instituições.
- A seção 14 permite extrair linhas preenchidas de atividades e participantes. São indicadores de prevenção/atendimento, não números de vítimas.
- Zeros explícitos são preservados. Células vazias não geram zeros nem observações fictícias. Tabelas com outros formatos continuam com extração pendente.
- Cada campo recebe uma situação em `disponibilidade`: disponível, disponível como período, não aplicável, ainda não extraído ou não localizado na parte examinada. Este último estado **não afirma que a informação inexista na fonte**.

As fichas exibem metadados como campos legíveis e links clicáveis, sem o texto literal `null`. Documentos não recebem campos numéricos vazios de uma observação estatística. A lista de arquivos relacionados mostra o que já foi examinado e o que permanece pendente. O histórico detalhado pode ser consultado em `/api/investigacoes`.

Nesta etapa foram examinados **15 PDFs**, elevando a base de 34 para **106 registros**: 79 observações estatísticas, 24 documentos e 3 contextos. As observações adicionais incluem 19 linhas de participantes em atividades e 38 células de vítimas atendidas, incluindo totais e componentes que não devem ser somados. A malha local cobre os 22 municípios presentes na base. Esses números descrevem esta execução; a consulta à API mostra o estado atualizado.

Exemplos conferidos: página do MJSP publicada em 11/09/2023, atualizada em 21/07/2026, com referência aos dados de 2025; notícia da SaferNet publicada em 04/07/2025; relatório nacional com período 2021–2023; relatório PAAHM Guarulhos do exercício 2024 com linhas de atividades de 200 e 300 participantes. Os registros do PAAHM identificam o município da unidade informante, sem criar um ponto de ocorrência.

Os arquivos e tabelas ainda não examinados permanecem indicados como pendentes. Na API, campos realmente não preenchidos podem continuar com o valor JSON `null`, acompanhado por `disponibilidade`: isso mantém os tipos corretos e não substitui ausência por zero. A interface apresenta o motivo correspondente.

### Leitura das representações territoriais

A cor de uma UF representa **quantidade de registros publicados com referência territorial**, sem somar valores de unidades incompatíveis. Não é mapa de prevalência, índice de risco ou número de vítimas.

Agregados municipais são consultáveis pelo filtro, pelas fichas e por seus limites territoriais coletados, sem marcadores artificiais em centroides. Clique numa área municipal para filtrar e aproximar. Somente coordenadas exatas fornecidas nos registros produzem marcadores. Documentos nacionais não viram pontos geográficos.

Os indicadores M021–M024 são contexto territorial; M025–M027 são contexto marítimo; M032–M034 documentam qualidade e limitações. A presença de um contexto não confirma um acontecimento. As relações do catálogo por fonte compartilhada são vínculos documentais, não relações entre indivíduos.

## Estrutura e API

```text
app.py                 CLI, SQLite, API HTTP e arquivos estáticos
collectors.py          Coleta, snapshots, perfil e importadores
documents.py           Verificação do catálogo e leitura documental pública
enrichment.py          Enriquecimento temporal, recuperação de links e extração de PDFs
web/                   Interface JavaScript/CSS/HTML
exemplos/              Mapeamento editável do Disque 100
tests/                 Testes de API, integridade e agregação
var/                   Banco, snapshots e downloads locais (gerados)
```

O catálogo original é lido da pasta vizinha `Observatorio_Trafico_Pessoas_Integrado_Atualizado_2026(1)/Observatorio_Trafico_Pessoas_Integrado_2026`. O HTML, a planilha e os arquivos originais são preservados.

Endpoints GET: `/api/resumo`, `/api/catalogo`, `/api/fontes`, `/api/mapa`, `/api/coletas`, `/api/recursos`, `/api/geografia`, `/api/localidades?uf=SP`, `/api/registros`, `/api/exportar.csv`. `/api/mapa` fornece cobertura das fontes, registros filtrados e contexto nacional separado.

Filtros de registros/exportação: `ambiente`, `uf`, `municipio_ibge`, `ano`, `tipo`, `tema`, `fonte_id`, `indicador`, `q`.

Para mudar o diretório de dados, defina `OBSERVATORIO_DATA` antes de executar. Para executar periodicamente, use o agendador do sistema chamando `python3 /CAMINHO/plataforma_brasil/app.py collect`.

## Verificação

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
node tests/test_format.js
python3 tests/browser_smoke.py
```

Os testes usam banco temporário e cobrem: catálogo completo/idempotente, precisão geográfica, exigência de evidência internacional, filtros, preservação de unidades, deduplicação municipal, exclusões, substituição de versões, rollback em falhas, API e exportação CSV.

## Próximas etapas

### Ampliação de extração e acompanhamento — 05/11/2026

A aba **Cobertura e pendências** consulta `/api/cobertura` e apresenta, por fonte:

- registros, estatísticas, documentos, unidades, anos referenciados e cobertura territorial;
- PDFs descobertos, examinados parcialmente e pendentes, com erros de acesso e necessidade de OCR;
- arquivos e tabelas com células extraídas, campos ainda não estruturados e períodos incompletos;
- os 34 indicadores, diferenciando fontes previstas no catálogo de registros efetivamente vinculados.

O botão **Atualizar situação** recarrega os dados após uma coleta. A cobertura é global, independente dos filtros do explorador. Os anos incluem publicações e referências; não comprovam uma série anual completa. Campos não aplicáveis não são contabilizados como pendências. PDFs são agrupados pela migração conhecida de URL do MJSP; documentos e observações de arquivos idênticos da mesma fonte são deduplicados pelo SHA256, preservando os endereços alternativos.

O extrator agora lê células explícitas das **tabelas 1–11 do relatório nacional 2021–2023**: perfis demográficos, inquéritos da PF, processos da Justiça Federal/Estadual, assuntos de processos do MPF, denúncias do Disque 100 e tipificações relativas a presos. As linhas por assunto do MPF não são somáveis; o extrator não calcula totais a partir delas. Nas tabelas com componentes aditivos, linhas inconsistentes com o total são recusadas. Percentuais e totais plurianuais não viram novas contagens anuais. Anos parciais assinalados com asterisco mantêm essa informação e a nota de cobertura. As fichas permitem abrir a página de evidência do PDF.

Para NETPs/PAAHMs, além das seções 1 e 14, a seção **13.1** permite extrair quantidades explícitas de materiais de campanha em formatos reconhecidos. Checkboxes, vazios e formatos não reconhecidos não geram números. A SaferNet passa a preservar separadamente os **423 links encaminhados ao MPF em 2024**, sem somá-los às denúncias recebidas.

```bash
python3 app.py enrich --source A01,A04,A21 --limit 140 --workers 6 --max-mb 20
python3 app.py enrich --source A01,A04,A21 --cached-only
python3 app.py collect --source A22
```

Antes da ampliação, foi criado um backup local `var/observatorio-antes-completude-*.sqlite3`. Os números anteriores neste guia descrevem execuções passadas; use a API de cobertura e o resumo para a situação atual.

### Pendências de conteúdo que permanecem

### Cadastro vigente MTE e Disque 100 de 2025-S2

`python3 app.py collect-mte-cadastro` baixa a versão atual do cadastro oficial de empregadores do MTE, valida o esquema e agrega **linhas do cadastro** por UF e ano da ação fiscal. Cada atualização substitui atomicamente a versão anterior, preserva SHA256, auditoria e data de coleta, e não importa dados individuais. São registros administrativos presentes no cadastro vigente: não representam a totalidade das fiscalizações anuais, pessoas resgatadas ou casos de tráfico. A versão examinada tinha 506 linhas, três sem UF/ano válido e 90 células agregadas.

O arquivo oficial do **segundo semestre de 2025** do Disque 100 foi analisado e importado com `exemplos/mapeamento_disque_2025_s2.json`: 85 linhas nas categorias de tráfico, 18 excluídas por campos de data/identificador/local, 16 repetidas dentro da célula e 24 células municipais. O ano indica cadastro; o semestre não é o ano completo, e o hash não é presumido como identificador de vítima. O arquivo baixado e sua origem podem ser conferidos pelo SHA256 na ficha.

- Extração dos demais documentos e construção de mais períodos municipais comparáveis.
- OCR dos arquivos sem camada de texto; extração das demais seções de perfis e aliciamento nos relatórios NETP/PAAHM.
- Outros períodos do Disque 100 e séries quantitativas específicas de MTE/SmartLab. A leitura documental dessas fontes não equivale à importação das séries.
- Ampliação dos dados digitais e revisão editorial dos vínculos dos indicadores: o cadastro de uma fonte não comprova a medição de todos os indicadores relacionados.
- Novos coletores brasileiros e recortes internacionais explicitamente sobre o Brasil.
- Fluxo de submissão, revisão e publicação de relatos; integração gov.br em etapa futura.
- M021 defasado e modelo preditivo somente após obter séries brasileiras comparáveis e definir o alvo. A aplicação não apresenta previsões ou correlações fabricadas.
