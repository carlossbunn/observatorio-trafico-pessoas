# Observatório de Tráfico de Pessoas — edição integrada (04/11/2026)

## Como abrir

1. Extraia o ZIP completo.
2. Abra `index.html` em um navegador moderno (Chrome, Firefox ou Edge). O HTML é **autônomo e offline**: não requer `pip install`, servidor, login nem bibliotecas externas.
3. Abra a seção **Todos os dados** para ver qualquer uma das tabelas, filtrar, ordenar, visualizar integralmente cada linha ou exportar o resultado.
4. Na seção **Cruzar tabelas**, selecione um modelo de junção ou indique duas tabelas e suas chaves. Clique **Executar cruzamento**.
5. Em **Data Science**, selecione um conjunto numérico, duas variáveis e, se necessário, um filtro de agrupamento; o gráfico e os coeficientes são atualizados sob demanda.
6. Para adicionar novos dados, use **Todos os dados → Importar arquivos locais**. CSVs com `;`, `,` ou tabulação e JSONs que contenham uma lista de objetos são aceitos. O processamento ocorre exclusivamente no navegador; os dados temporários são descartados ao recarregar. Exporte os resultados que desejar guardar.

## O que o pacote contém

- `index.html` — página web única com todas as tabelas embutidas, sem dependências.
- `dados_completos_integrados.json` — acervo estruturado, incluindo listas originais e derivadas.
- `tabela_completa_integrada_2026.xlsx` — planilha principal **atualizada**, com 13 abas.
- `dados/*.csv` — exportações por tabela e o CSV original enviado.
- `auditoria_integracao.json` — métricas de deduplicação e verificação das chaves.
- `relatorio_metodologico_trafico_pessoas_2026.pdf` — relatório elaborado na etapa anterior. Ele descreve o levantamento original; a presente edição adiciona o mecanismo de junções e as arestas documentais.
- `FONTES_E_LINKS.md` — catálogo documental com URLs do levantamento anterior.
- `codigo_fonte_painel.js` — código JavaScript para edição técnica; o HTML já contém uma cópia executável desse código.

## Contagem e semântica

| Conjunto | Linhas | Unidade de cada linha |
|---|---:|---|
| Fontes | 59 | instituição/publicação/serviço catalogado |
| Indicadores | 34 | variável conceitual de risco ou contexto |
| CSV do usuário | 34 | indicador recebido, idêntico ao canônico |
| Perguntas | 18 | pergunta pública documentada ou analítica |
| Cruzamentos propostos | 12 | hipótese metodológica |
| Evidências | 6 | achado de publicação, com unidade e limite |
| Série Eurostat | 11 | ano de percentuais de exploração (2014–2024) |
| Observações oficiais | 32 | valor agregado com unidade, local e referência |
| Tabela de hipóteses | 117 | indicador × proposta de cruzamento |
| **Registros unificados** | **289** | 1 registro original não duplicado entre os 8 conjuntos originais |
| **Arestas documentais** | **899** | 1 ligação explícita entre IDs, fonte, pergunta ou hipótese |

O CSV enviado contém **34/34 indicadores previamente existentes**, sem diferenças de conteúdo. Sua importação acrescentou **zero indicadores novos**. O arquivo foi preservado como referência de origem, sem duplicação na tabela canônica.

## Junções e comparabilidade

- `M001` = indicador; `C01` = hipótese de cruzamento; `Q01` = pergunta; `A01` e `F01` = fonte. O uso de chaves separadas por ponto e vírgula é suportado.
- Um join pode multiplicar linhas em relação muitos-para-muitos. Essas linhas **não são novas vítimas, denúncias nem observações independentes**.
- Correlação de Pearson e Spearman é calculada apenas com pares válidos; tabelas conceituais e coleções quantitativas heterogêneas não são automaticamente correlacionadas.
- O resultado inicial `r ≈ 0,895` descreve associação temporal entre **ano** e **participação percentual de trabalho forçado** na série do Eurostat incorporada. É uma correlação descritiva, não causal.
- As 59 fontes estão **documentadas**, mas os microdados completos de todas as APIs não foram coletados neste pacote. Portanto não é um banco universal de todos os casos registrados no mundo.

## Licença, privacidade e segurança

Mantenha as regras de licença e uso próprias de cada fonte. Não inclua dados pessoais de vítimas, CPFs, contatos, endereços residenciais ou mensagens privadas sem base legal. Este pacote não atribui conduta criminosa a pessoas ou empresas; sua função é explorar indicadores e fontes.

Arquivos são disponibilizados para análise local. O HTML não envia arquivos a servidores, não chama APIs e não utiliza bibliotecas externas.
