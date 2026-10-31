import argparse
import getpass
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
OBRAS_CSV = DATA_DIR / "obras-nao-pub-brasileiras-2020-2026.csv"
PROD_CSV = DATA_DIR / "produtores-de-obras-nao-publicitarias-brasileiras.csv"
RELATORIO = Path("relatorio_qualidade.md")

RE_CNPJ = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
RE_CPB = re.compile(r"^B\d{13}$")


# ----------------------------------------------------------------- helpers
def limpa(s: str) -> str:
    """Tira espacos nas pontas e colapsa espacos repetidos."""
    return re.sub(r"\s+", " ", (s or "").strip())


def chave(s: str) -> str:
    """Chave de comparacao: sem acento, maiuscula, sem espaco extra.
    Imita a collation utf8mb4_unicode_ci (evita violar UNIQUE no banco)."""
    s = unicodedata.normalize("NFKD", limpa(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


def so_digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def cnpj14(s: str):
    """Devolve o CNPJ com 14 digitos ou None.
    Trata: mascara com 15 digitos (zero a esquerda, comum na base de produtores),
    sufixo espurio (ex.: '...142x') e o placeholder 00000000000000."""
    if not any(ch.isdigit() for ch in s):
        return None
    d = so_digitos(s)
    if len(d) == 15 and d.startswith("0"):
        d = d[1:]
    if len(d) != 14 or set(d) == {"0"}:
        return None
    return d


# Correcao de acentuacao/grafia dos paises (chave = grafia original sem acento)
PAISES_CORRIGIDOS = {
    "FRANCA": "FRANÇA",
    "INDIA": "ÍNDIA",
    "ISLANDIA": "ISLÂNDIA",
    "ITALIA": "ITÁLIA",
    "JAPAO": "JAPÃO",
    "PAISES BAIXOS (HOLANDA)": "PAÍSES BAIXOS (HOLANDA)",
    "HUNGRIA, REPUBLICA DA": "HUNGRIA, REPÚBLICA DA",
    "CABO VERDE, REPUBLICA DE": "CABO VERDE, REPÚBLICA DE",
    "CHINA, REPUBLICA POPULAR": "CHINA, REPÚBLICA POPULAR",
    "BURKINA FASSO": "BURKINA FASO",
}


def corrige_pais(s: str) -> str:
    s = limpa(s)
    return PAISES_CORRIGIDOS.get(chave(s), s)


def mais_frequente(valores):
    """Forma de escrita mais frequente (empate: ordem alfabetica)."""
    c = Counter(valores)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


class Dominio:
    """Tabela de dominio: valor (por chave normalizada) -> id sequencial."""

    def __init__(self, valores):
        grupos = {}
        for v in valores:
            v = limpa(v)
            if v:
                grupos.setdefault(chave(v), []).append(v)
        self.nome = {k: mais_frequente(v) for k, v in grupos.items()}
        ordenadas = sorted(self.nome)
        self.id = {k: i for i, k in enumerate(ordenadas, start=1)}

    def get(self, valor):
        valor = limpa(valor)
        return self.id[chave(valor)] if valor else None

    def linhas(self):
        return [(self.id[k], self.nome[k]) for k in sorted(self.id, key=self.id.get)]


# ----------------------------------------------------------- transformacao
def transforma():
    rel = []  # linhas do relatorio de qualidade

    obras = pd.read_csv(OBRAS_CSV, sep=";", dtype=str, encoding="utf-8-sig",
                        keep_default_na=False)
    prod = pd.read_csv(PROD_CSV, sep=";", dtype=str, encoding="utf-8",
                       keep_default_na=False)
    rel.append("## 1. Esquema original e volume\n")
    rel.append(f"- Base de obras: {len(obras)} linhas, {obras.shape[1]} colunas (1 linha por CPB)")
    rel.append(f"- Base de produtores: {len(prod)} linhas, {prod.shape[1]} colunas "
               f"(1 linha por par produtor x obra; a base cobre todos os anos, nao so 2020-2026)\n")

    # ---- nulos / inconsistencias (obras)
    rel.append("## 2. Nulos e inconsistencias - obras\n")
    rel.append("| Coluna | Vazios |\n|---|---|")
    for c in obras.columns:
        n = int((obras[c].str.strip() == "").sum())
        if n:
            rel.append(f"| {c} | {n} |")
    rel.append("")
    rel.append(f"- CPB duplicado: {int(obras.CPB.duplicated().sum())}")
    rel.append(f"- CPB fora do padrao B+13 digitos: {int((~obras.CPB.str.match(RE_CPB)).sum())}")
    rel.append(f"- Subtipo com valor 'NÃO INFORMADO' (placeholder no lugar de nulo): "
               f"{int((obras.SUBTIPO_OBRA == 'NÃO INFORMADO').sum())}")
    rel.append(f"- Segmento 'INDEFINIDO' / 'NENHUMA DAS OPÇÕES': "
               f"{int(obras.SEGMENTO_DESTINACAO_INICIAL.isin(['INDEFINIDO', 'NENHUMA DAS OPÇÕES']).sum())}")
    rel.append(f"- Requerente 'PESSOA FÍSICA' no campo CNPJ (sem CNPJ): "
               f"{int((obras.CNPJ_REQUERENTE == 'PESSOA FÍSICA').sum())}")
    rel.append(f"- Titulos com aspas duplicadas/escapadas: "
               f"{int(obras.TITULO_ORIGINAL.str.contains(chr(34)).sum())}\n")

    # ---- produtores: filtra para o recorte das obras
    rel.append("## 3. Nulos e inconsistencias - produtores\n")
    cpb_ruim = prod[~prod.CPB.str.match(RE_CPB)]
    rel.append(f"- CPB fora do padrao (13 caracteres em vez de 14): {len(cpb_ruim)} "
               f"({', '.join(cpb_ruim.CPB)}) - sao obras antigas, fora do recorte")
    rel.append(f"- Linhas exatamente duplicadas: {int(prod.duplicated().sum())}")
    rel.append(f"- CNPJ 'PESSOA FÍSICA': {int((prod.CNPJ_PRODUTOR == 'PESSOA FÍSICA').sum())}; "
               f"'NÃO INFORMADO': {int((prod.CNPJ_PRODUTOR == 'NÃO INFORMADO').sum())}")
    rel.append(f"- Pais 'Não Informado': {int((prod.PAIS_PRODUTOR == 'Não Informado').sum())}")
    rel.append("- Paises com grafia sem acento (ex.: FRANCA, ITALIA, JAPAO, INDIA) misturados com "
               "grafia acentuada (ex.: MÉXICO)")
    fora = ~prod.CPB.isin(obras.CPB)
    rel.append(f"- Linhas de produtores cujo CPB nao esta na base de obras 2020-2026: "
               f"{int(fora.sum())} (descartadas)")
    sem_prod = int((~obras.CPB.isin(prod.CPB)).sum())
    rel.append(f"- Obras sem nenhum produtor na base de produtores: {sem_prod}")
    prod["_cnpj"] = prod.CNPJ_PRODUTOR.map(cnpj14)
    rel.append(f"- CNPJ de produtor com 15 digitos (zero a esquerda, fora do formato do dicionario): "
               f"{int(prod.CNPJ_PRODUTOR.map(lambda x: len(so_digitos(x)) == 15).sum())}")
    ruim = prod.CNPJ_PRODUTOR.map(lambda x: bool(re.search(r"\d", x)) and cnpj14(x) is None
                                  or bool(re.search(r"\d[^\d]+$", x)))
    rel.append(f"- CNPJ de produtor zerado (00000000000000) ou com sufixo invalido ('x'): {int(ruim.sum())}")
    com_cnpj = prod[prod._cnpj.notna()]
    g = com_cnpj.groupby("_cnpj").PRODUTOR.nunique()
    rel.append(f"- CNPJs com mais de um nome de produtor (sinonimos): {int((g > 1).sum())}\n")

    prod = prod[~fora].drop(columns="_cnpj").drop_duplicates().copy()
    prod["PAIS_PRODUTOR"] = prod.PAIS_PRODUTOR.map(corrige_pais)

    # ---------------- dominios
    d_tipo = Dominio(obras.TIPO_OBRA)
    d_sub = Dominio(obras.SUBTIPO_OBRA)  # vazio fica de fora -> NULL
    d_cla = Dominio(obras.CLASSIFICACAO_OBRA)
    d_org = Dominio(obras.ORGANIZACAO_TEMPORAL)
    d_seg = Dominio(obras.SEGMENTO_DESTINACAO_INICIAL)
    d_uf = Dominio(obras.UF_REQUERENTE)
    paises = prod.PAIS_PRODUTOR.where(prod.PAIS_PRODUTOR.map(chave) != "NAO INFORMADO", "")
    d_pais = Dominio(paises)

    # ---------------- municipio (nome + uf)
    mun_grupos = {}
    for nome, uf in zip(obras.MUNICIPIO_REQUERENTE, obras.UF_REQUERENTE):
        mun_grupos.setdefault((chave(nome), d_uf.get(uf)), []).append(limpa(nome))
    mun_nome = {k: mais_frequente(v) for k, v in mun_grupos.items()}
    mun_id = {k: i for i, k in enumerate(sorted(mun_nome, key=lambda k: (k[1], k[0])), start=1)}

    # ---------------- requerente
    req = {}  # chave_unica -> dict
    req_de_obra = {}
    for r in obras.itertuples(index=False):
        mid = mun_id[(chave(r.MUNICIPIO_REQUERENTE), d_uf.get(r.UF_REQUERENTE))]
        if RE_CNPJ.match(r.CNPJ_REQUERENTE):
            cnpj = so_digitos(r.CNPJ_REQUERENTE)
            k = ("PJ", cnpj)
            tipo, chave_sem = "PJ", None
        else:
            cnpj = None
            chave_sem = f"{chave(r.REQUERENTE)}|{mid}"
            k = ("PF", chave_sem)
            tipo = "PF"
        e = req.setdefault(k, {"tipo": tipo, "cnpj": cnpj, "nomes": [], "mid": mid,
                               "chave_sem": chave_sem})
        e["nomes"].append(limpa(r.REQUERENTE))
        req_de_obra[r.CPB] = k
    req_id = {k: i for i, k in enumerate(sorted(req), start=1)}

    # ---------------- produtor (+ nomes alternativos)
    pr = {}
    prod_de_par = set()
    for r in prod.itertuples(index=False):
        pais_id = d_pais.get(r.PAIS_PRODUTOR) if chave(r.PAIS_PRODUTOR) != "NAO INFORMADO" else None
        nome = limpa(r.PRODUTOR)
        c = r.CNPJ_PRODUTOR.strip()
        cnpj = cnpj14(c)
        if cnpj:
            k, tipo, chave_sem = ("PJ", cnpj), "PJ", None
        else:
            tipo = "PF" if chave(c) == "PESSOA FISICA" else "NAO_INFORMADO"
            sigla = "PF" if tipo == "PF" else "NI"
            chave_sem = f"{sigla}|{chave(nome)}|{pais_id or 0}"
            k = (sigla, chave_sem)
        e = pr.setdefault(k, {"tipo": tipo, "cnpj": cnpj, "nomes": [], "pais": pais_id,
                              "chave_sem": chave_sem})
        e["nomes"].append(nome)
        # pais do produtor com CNPJ: o mais frequente
        e.setdefault("paises", []).append(pais_id)
        prod_de_par.add((r.CPB, k))
    prod_id = {k: i for i, k in enumerate(sorted(pr), start=1)}

    produtor_rows, alt_rows = [], []
    n_alt = 0
    for k, e in sorted(pr.items(), key=lambda kv: prod_id[kv[0]]):
        canon = mais_frequente(e["nomes"])
        pais = mais_frequente([p for p in e["paises"] if p is not None]) if any(
            p is not None for p in e["paises"]) else None
        produtor_rows.append((prod_id[k], e["tipo"], e["cnpj"], canon, pais, e["chave_sem"]))
        vistos = {chave(canon)}
        for n in sorted(set(e["nomes"])):
            if chave(n) not in vistos:
                vistos.add(chave(n))
                alt_rows.append((len(alt_rows) + 1, prod_id[k], n))
                n_alt += 1

    requerente_rows = []
    for k, e in sorted(req.items(), key=lambda kv: req_id[kv[0]]):
        requerente_rows.append((req_id[k], e["tipo"], e["cnpj"], mais_frequente(e["nomes"]),
                                e["mid"], e["chave_sem"]))

    # ---------------- obra
    def num(s):
        s = s.strip()
        return None if s == "" else s

    obra_rows = []
    for r in obras.itertuples(index=False):
        d, m, a = r.DATA_EMISSAO_CPB.split("/")
        coprod = 1 if chave(r.COPRODUCAO_INTERNACIONAL) == "SIM" else 0
        obra_rows.append((
            r.CPB, limpa(r.TITULO_ORIGINAL), f"{a}-{m}-{d}", limpa(r.SITUACAO_OBRA),
            d_tipo.get(r.TIPO_OBRA), d_sub.get(r.SUBTIPO_OBRA), d_cla.get(r.CLASSIFICACAO_OBRA),
            d_org.get(r.ORGANIZACAO_TEMPORAL), d_seg.get(r.SEGMENTO_DESTINACAO_INICIAL),
            r.DURACAO_TOTAL_MINUTOS.replace(",", "."),
            num(r.QUANTIDADE_EPISODIOS), num(r.ANO_PRODUCAO_INICIAL), num(r.ANO_PRODUCAO_FINAL),
            coprod, req_id[req_de_obra[r.CPB]],
        ))

    op_rows = sorted((cpb, prod_id[k]) for cpb, k in prod_de_par)

    uf_rows = [(i, nome) for i, nome in d_uf.linhas()]
    mun_rows = [(mun_id[k], mun_nome[k], k[1]) for k in sorted(mun_id, key=mun_id.get)]

    tabelas = {
        "uf": uf_rows,
        "pais": d_pais.linhas(),
        "municipio": mun_rows,
        "tipo_obra": d_tipo.linhas(),
        "subtipo_obra": d_sub.linhas(),
        "classificacao": d_cla.linhas(),
        "organizacao_temporal": d_org.linhas(),
        "segmento": d_seg.linhas(),
        "requerente": requerente_rows,
        "produtor": produtor_rows,
        "produtor_nome_alternativo": alt_rows,
        "obra": obra_rows,
        "obra_produtor": op_rows,
    }

    rel.append("## 4. Tratamentos aplicados\n")
    rel.append("- Espacos extras removidos; comparacao sem acento/maiuscula para evitar duplicatas")
    rel.append("- CNPJ de produtor normalizado para 14 digitos (remove zero extra e sufixo 'x'); CNPJ zerado vira NAO_INFORMADO")
    rel.append("- CNPJ guardado so com 14 digitos; 'PESSOA FÍSICA' / 'NÃO INFORMADO' viram CNPJ nulo + tipo_pessoa")
    rel.append("- Subtipo vazio -> NULL; ano inicial vazio -> NULL; episodios e ano final vazios -> NULL")
    rel.append("- Duracao: virgula decimal -> ponto; data dd/MM/yyyy -> yyyy-MM-dd; SIM/NÃO -> booleano")
    rel.append("- Pais 'Não Informado' -> NULL")
    rel.append(f"- Grafia de paises corrigida por mapeamento ({len(PAISES_CORRIGIDOS)} regras, ex.: FRANCA -> FRANÇA, JAPAO -> JAPÃO)")
    rel.append("- Produtores filtrados para os CPBs da base de obras; pares (CPB, produtor) deduplicados")
    rel.append(f"- Nome canonico do produtor = mais frequente; {n_alt} nomes alternativos gravados\n")
    rel.append("## 5. Contagem prevista por tabela\n")
    rel.append("| Tabela | Linhas |\n|---|---|")
    for t, rows in tabelas.items():
        rel.append(f"| {t} | {len(rows)} |")
    return tabelas, "\n".join(rel) + "\n"


# --------------------------------------------------- validacao em Python
def valida(t):
    """Confere unicidade, FK e CHECKs do schema antes de tocar no banco."""
    erros = []

    def unico(nome, vals):
        vals = [v for v in vals if v is not None]
        if len(vals) != len(set(vals)):
            erros.append(f"UNIQUE violado em {nome}")

    for tab in ("tipo_obra", "subtipo_obra", "classificacao", "organizacao_temporal",
                "segmento", "pais"):
        unico(tab, [chave(n) for _, n in t[tab]])
    unico("uf", [s for _, s in t["uf"]])
    unico("municipio", [(chave(n), u) for _, n, u in t["municipio"]])
    unico("requerente.cnpj", [r[2] for r in t["requerente"]])
    unico("requerente.chave_sem_cnpj", [r[5] for r in t["requerente"]])
    unico("produtor.cnpj", [r[2] for r in t["produtor"]])
    unico("produtor.chave_sem_cnpj", [r[5] for r in t["produtor"]])
    unico("alt", [(a, chave(n)) for _, a, n in t["produtor_nome_alternativo"]])

    ids = {k: {r[0] for r in v} for k, v in t.items() if k not in ("obra", "obra_produtor")}
    for r in t["municipio"]:
        if r[2] not in ids["uf"]:
            erros.append("FK municipio.uf")
    for r in t["requerente"]:
        if r[4] not in ids["municipio"]:
            erros.append("FK requerente.municipio")
        if not ((r[1] == "PJ" and r[2]) or (r[1] == "PF" and r[2] is None)):
            erros.append("CHECK requerente")
    for r in t["produtor"]:
        if r[4] is not None and r[4] not in ids["pais"]:
            erros.append("FK produtor.pais")
        if not ((r[1] == "PJ" and r[2]) or (r[1] != "PJ" and r[2] is None)):
            erros.append("CHECK produtor")
        if len(r[3]) > 150 or (r[5] and len(r[5]) > 170):
            erros.append("tamanho produtor")
    cpbs = set()
    for o in t["obra"]:
        cpbs.add(o[0])
        if not RE_CPB.match(o[0]): erros.append("CHECK cpb")
        if len(o[1]) > 100: erros.append("titulo > 100")
        for i, tab in ((4, "tipo_obra"), (6, "classificacao"), (7, "organizacao_temporal"),
                       (8, "segmento"), (14, "requerente")):
            if o[i] not in ids[tab]: erros.append(f"FK obra.{tab}")
        if o[5] is not None and o[5] not in ids["subtipo_obra"]: erros.append("FK obra.subtipo")
        if o[11] and o[12] and int(o[12]) < int(o[11]): erros.append("CHECK anos")
        if float(o[9]) < 0: erros.append("CHECK duracao")
    if len(cpbs) != len(t["obra"]): erros.append("CPB duplicado")
    for cpb, pid in t["obra_produtor"]:
        if cpb not in cpbs or pid not in ids["produtor"]:
            erros.append("FK obra_produtor")
    return sorted(set(erros))


# ------------------------------------------------------------ carga (DB)
ORDEM = ["uf", "pais", "municipio", "tipo_obra", "subtipo_obra", "classificacao",
         "organizacao_temporal", "segmento", "requerente", "produtor",
         "produtor_nome_alternativo", "obra", "obra_produtor"]

SQL = {
    "uf": "INSERT INTO uf (id_uf, sigla) VALUES (%s,%s)",
    "pais": "INSERT INTO pais (id_pais, nome) VALUES (%s,%s)",
    "municipio": "INSERT INTO municipio (id_municipio, nome, id_uf) VALUES (%s,%s,%s)",
    "tipo_obra": "INSERT INTO tipo_obra (id_tipo_obra, nome) VALUES (%s,%s)",
    "subtipo_obra": "INSERT INTO subtipo_obra (id_subtipo_obra, nome) VALUES (%s,%s)",
    "classificacao": "INSERT INTO classificacao (id_classificacao, nome) VALUES (%s,%s)",
    "organizacao_temporal": "INSERT INTO organizacao_temporal (id_organizacao_temporal, nome) VALUES (%s,%s)",
    "segmento": "INSERT INTO segmento (id_segmento, nome) VALUES (%s,%s)",
    "requerente": "INSERT INTO requerente (id_requerente, tipo_pessoa, cnpj, nome, id_municipio, chave_sem_cnpj) VALUES (%s,%s,%s,%s,%s,%s)",
    "produtor": "INSERT INTO produtor (id_produtor, tipo_pessoa, cnpj, nome, id_pais, chave_sem_cnpj) VALUES (%s,%s,%s,%s,%s,%s)",
    "produtor_nome_alternativo": "INSERT INTO produtor_nome_alternativo (id_nome_alternativo, id_produtor, nome) VALUES (%s,%s,%s)",
    "obra": ("INSERT INTO obra (cpb, titulo, data_emissao, situacao, id_tipo_obra, id_subtipo_obra, "
             "id_classificacao, id_organizacao_temporal, id_segmento, duracao_minutos, qtd_episodios, "
             "ano_prod_inicial, ano_prod_final, coproducao_internacional, id_requerente) "
             "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"),
    "obra_produtor": "INSERT INTO obra_produtor (cpb, id_produtor) VALUES (%s,%s)",
}


def carrega(tabelas, reset):
    import pymysql

    senha = os.environ.get("DB_PASSWORD") or getpass.getpass("Senha do usuario do banco: ")
    con = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"), port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "etl_obras"), password=senha,
        database=os.environ.get("DB_NAME", "mapa_obras"), charset="utf8mb4", autocommit=False)
    try:
        cur = con.cursor()
        if reset:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for t in reversed(ORDEM):
                cur.execute(f"TRUNCATE TABLE {t}")
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        else:
            for t in ORDEM:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                if cur.fetchone()[0]:
                    sys.exit(f"Tabela {t} ja tem dados. Use --reset para recarregar.")
        for t in ORDEM:
            rows = tabelas[t]
            for i in range(0, len(rows), 2000):
                cur.executemany(SQL[t], rows[i:i + 2000])
            print(f"  {t}: {len(rows)} linhas")
        con.commit()

        print("\nValidacao no banco (esperado x encontrado):")
        ok = True
        for t in ORDEM:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            n = cur.fetchone()[0]
            flag = "OK" if n == len(tabelas[t]) else "DIVERGE"
            ok &= n == len(tabelas[t])
            print(f"  {t:28s} {len(tabelas[t]):>7d} x {n:>7d}  {flag}")
        cur.execute("SELECT COUNT(*) FROM obra o LEFT JOIN requerente r "
                    "ON r.id_requerente=o.id_requerente WHERE r.id_requerente IS NULL")
        print("  obras sem requerente:", cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM obra o WHERE NOT EXISTS "
                    "(SELECT 1 FROM obra_produtor p WHERE p.cpb=o.cpb)")
        print("  obras sem produtor:", cur.fetchone()[0])
        sys.exit(0 if ok else 1)
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="nao conecta ao banco")
    ap.add_argument("--reset", action="store_true", help="limpa as tabelas antes de carregar")
    a = ap.parse_args()

    tabelas, relatorio = transforma()
    erros = valida(tabelas)
    relatorio += "\n## 6. Validacao previa (unicidade, FKs, CHECKs)\n\n" + (
        "- Nenhuma violacao encontrada\n" if not erros else "".join(f"- {e}\n" for e in erros))
    RELATORIO.write_text("# Relatorio de qualidade e ETL\n\n" + relatorio, encoding="utf-8")
    print(f"Relatorio gravado em {RELATORIO}")
    for t in ORDEM:
        print(f"  {t:28s} {len(tabelas[t]):>7d}")
    if erros:
        sys.exit("Violacoes encontradas: " + "; ".join(erros))
    if not a.dry_run:
        carrega(tabelas, a.reset)


if __name__ == "__main__":
    main()
