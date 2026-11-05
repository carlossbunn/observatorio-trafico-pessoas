# Observatório Brasil — tráfico de pessoas

Plataforma local de consulta a fontes públicas, informações territoriais e evidências sobre tráfico de pessoas, com ambientes real e virtual. Inclui catálogo de fontes, filtros, dados por instituição, recrutamento digital, cobertura e referências documentais.

## Executar

Requisitos: Python 3.10 ou superior. Os coletores de PDF também precisam do utilitário `pdftotext` (Poppler). O aplicativo principal usa a biblioteca padrão do Python, sem instalação de pacotes.

```bash
git clone https://github.com/carlossbunn/observatorio-trafico-pessoas.git
cd observatorio-trafico-pessoas/plataforma_brasil
python3 app.py serve
```

Abra **http://127.0.0.1:8765**. Para outra porta, use `python3 app.py serve --port 8766`.

## Popular a base

A primeira execução cria uma base SQLite local com o catálogo. **O banco, os dados coletados, downloads e snapshots do ambiente de desenvolvimento não são incluídos neste repositório.** Para recriar dados a partir das fontes oficiais:

```bash
python3 app.py collect --source A11
python3 app.py collect --source A22
python3 app.py collect-mte-cadastro
python3 app.py collect-perfil-recente
python3 app.py import-recrutamento exemplos/recrutamento_fontes_publicas.json
```

Esses comandos acessam fontes externas e podem falhar se uma publicação ou serviço estiver indisponível. O coletor A11 fornece localidades e malhas geográficas; o comando `collect-perfil-recente` consulta os relatórios oficiais de 2024 e 2025. Os demais dados e períodos exigem coletas adicionais ou importações descritas no [guia da plataforma](plataforma_brasil/README.md), incluindo a importação explícita dos arquivos do Disque 100. Uma instalação nova não reproduz automaticamente todas as informações da base de desenvolvimento.

## Estrutura

- [`plataforma_brasil/`](plataforma_brasil/) — aplicativo Python, interface, coletores e testes.
- [`Observatorio_Trafico_Pessoas_Integrado_Atualizado_2026(1)/`](Observatorio_Trafico_Pessoas_Integrado_Atualizado_2026%281%29/) — catálogo e painel original utilizados pela plataforma.

## Verificação

Na pasta `plataforma_brasil`:

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
node tests/test_format.js
```

O teste `tests/browser_smoke.py` requer Chrome/Chromium e uma base previamente populada com os registros específicos utilizados pelo teste.

Denúncias, registros administrativos, vítimas, atendimentos e documentos têm unidades diferentes. A presença de um sinal em uma oferta não comprova fraude ou tráfico; confira a fonte e os limites em cada ficha.
