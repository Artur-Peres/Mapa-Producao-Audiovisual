# Relatorio de qualidade e ETL

## 1. Esquema original e volume

- Base de obras: 23495 linhas, 18 colunas (1 linha por CPB)
- Base de produtores: 74568 linhas, 5 colunas (1 linha por par produtor x obra; a base cobre todos os anos, nao so 2020-2026)

## 2. Nulos e inconsistencias - obras

| Coluna | Vazios |
|---|---|
| SUBTIPO_OBRA | 20011 |
| QUANTIDADE_EPISODIOS | 17901 |
| ANO_PRODUCAO_INICIAL | 2 |
| ANO_PRODUCAO_FINAL | 17901 |

- CPB duplicado: 0
- CPB fora do padrao B+13 digitos: 0
- Subtipo com valor 'NÃO INFORMADO' (placeholder no lugar de nulo): 4
- Segmento 'INDEFINIDO' / 'NENHUMA DAS OPÇÕES': 833
- Requerente 'PESSOA FÍSICA' no campo CNPJ (sem CNPJ): 4718
- Titulos com aspas duplicadas/escapadas: 64

## 3. Nulos e inconsistencias - produtores

- CPB fora do padrao (13 caracteres em vez de 14): 2 (B600566000000, B130174300000) - sao obras antigas, fora do recorte
- Linhas exatamente duplicadas: 0
- CNPJ 'PESSOA FÍSICA': 16075; 'NÃO INFORMADO': 2435
- Pais 'Não Informado': 400
- Paises com grafia sem acento (ex.: FRANCA, ITALIA, JAPAO, INDIA) misturados com grafia acentuada (ex.: MÉXICO)
- Linhas de produtores cujo CPB nao esta na base de obras 2020-2026: 45980 (descartadas)
- Obras sem nenhum produtor na base de produtores: 801
- CNPJ de produtor com 15 digitos (zero a esquerda, fora do formato do dicionario): 56034
- CNPJ de produtor zerado (00000000000000) ou com sufixo invalido ('x'): 24
- CNPJs com mais de um nome de produtor (sinonimos): 101

## 4. Tratamentos aplicados

- Espacos extras removidos; comparacao sem acento/maiuscula para evitar duplicatas
- CNPJ de produtor normalizado para 14 digitos (remove zero extra e sufixo 'x'); CNPJ zerado vira NAO_INFORMADO
- CNPJ guardado so com 14 digitos; 'PESSOA FÍSICA' / 'NÃO INFORMADO' viram CNPJ nulo + tipo_pessoa
- Subtipo vazio -> NULL; ano inicial vazio -> NULL; episodios e ano final vazios -> NULL
- Duracao: virgula decimal -> ponto; data dd/MM/yyyy -> yyyy-MM-dd; SIM/NÃO -> booleano
- Pais 'Não Informado' -> NULL
- Grafia de paises corrigida por mapeamento (10 regras, ex.: FRANCA -> FRANÇA, JAPAO -> JAPÃO)
- Produtores filtrados para os CPBs da base de obras; pares (CPB, produtor) deduplicados
- Nome canonico do produtor = mais frequente; 35 nomes alternativos gravados

## 5. Contagem prevista por tabela

| Tabela | Linhas |
|---|---|
| uf | 27 |
| pais | 44 |
| municipio | 664 |
| tipo_obra | 10 |
| subtipo_obra | 4 |
| classificacao | 3 |
| organizacao_temporal | 4 |
| segmento | 10 |
| requerente | 7431 |
| produtor | 10110 |
| produtor_nome_alternativo | 35 |
| obra | 23495 |
| obra_produtor | 28586 |

## 6. Validacao previa (unicidade, FKs, CHECKs)

- Nenhuma violacao encontrada
