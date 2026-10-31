"""Camada de dados do dashboard (sem Streamlit): consultas SQL e agregacoes em pandas."""
import pandas as pd

OBRAS_SQL = """
SELECT o.cpb, o.titulo, o.data_emissao, t.nome AS tipo, sg.nome AS segmento,
       cl.nome AS classificacao, ot.nome AS organizacao, o.duracao_minutos,
       o.coproducao_internacional AS coprod, r.id_requerente, r.nome AS requerente,
       u.sigla AS uf
FROM obra o
JOIN tipo_obra t              ON t.id_tipo_obra = o.id_tipo_obra
JOIN segmento sg              ON sg.id_segmento = o.id_segmento
JOIN classificacao cl         ON cl.id_classificacao = o.id_classificacao
JOIN organizacao_temporal ot  ON ot.id_organizacao_temporal = o.id_organizacao_temporal
JOIN requerente r             ON r.id_requerente = o.id_requerente
JOIN municipio m              ON m.id_municipio = r.id_municipio
JOIN uf u                     ON u.id_uf = m.id_uf
"""

OP_SQL = """
SELECT op.cpb, p.id_produtor, p.nome AS produtor, p.tipo_pessoa
FROM obra_produtor op
JOIN produtor p ON p.id_produtor = op.id_produtor
"""

# Centro aproximado (capital) de cada UF, para o mapa de bolhas
UF_COORD = {
    "AC": (-9.97, -67.81), "AL": (-9.67, -35.74), "AP": (0.03, -51.07), "AM": (-3.12, -60.02),
    "BA": (-12.97, -38.51), "CE": (-3.73, -38.52), "DF": (-15.78, -47.93), "ES": (-20.32, -40.34),
    "GO": (-16.68, -49.25), "MA": (-2.53, -44.30), "MT": (-15.60, -56.10), "MS": (-20.44, -54.65),
    "MG": (-19.92, -43.94), "PA": (-1.46, -48.50), "PB": (-7.12, -34.86), "PR": (-25.43, -49.27),
    "PE": (-8.05, -34.88), "PI": (-5.09, -42.80), "RJ": (-22.91, -43.17), "RN": (-5.79, -35.21),
    "RS": (-30.03, -51.23), "RO": (-8.76, -63.90), "RR": (2.82, -60.67), "SC": (-27.59, -48.55),
    "SP": (-23.55, -46.63), "SE": (-10.91, -37.07), "TO": (-10.18, -48.33),
}


def _df(cur, sql):
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)


def carregar(con):
    """Le o banco e devolve (obras, obra_produtor) como DataFrames prontos para filtrar."""
    cur = con.cursor()
    obras = _df(cur, OBRAS_SQL)
    op = _df(cur, OP_SQL)
    obras["data_emissao"] = pd.to_datetime(obras["data_emissao"])
    obras["ano"] = obras["data_emissao"].dt.year
    obras["duracao_minutos"] = obras["duracao_minutos"].astype(float)
    obras["coprod"] = obras["coprod"].astype(int).map({1: "Sim", 0: "Não"})
    return obras, op


def contagem(df, coluna, topo=None, rotulo=None):
    """Quantidade de linhas por valor de `coluna`, ordenada do maior para o menor."""
    s = df[coluna].value_counts()
    if topo:
        s = s.head(topo)
    return s.rename_axis(rotulo or coluna).reset_index(name="obras")


def obras_por_ano(df):
    return df.groupby("ano").size().reset_index(name="obras")


def ranking_produtores(op_filtrado, topo=10):
    """Top produtores por numero de obras (ignora produtores nao identificados)."""
    d = op_filtrado[op_filtrado["tipo_pessoa"] != "NAO_INFORMADO"]
    r = d.groupby(["id_produtor", "produtor"]).size().reset_index(name="obras")
    return r.sort_values(["obras", "produtor"], ascending=[False, True]).head(topo)[["produtor", "obras"]]


def ranking_requerentes(df, topo=10):
    r = df.groupby(["id_requerente", "requerente"]).size().reset_index(name="obras")
    return r.sort_values(["obras", "requerente"], ascending=[False, True]).head(topo)[["requerente", "obras"]]


def mapa_uf(df):
    """Uma linha por UF com latitude/longitude e raio da bolha (proporcional a raiz da contagem)."""
    c = contagem(df, "uf", rotulo="uf")
    c["latitude"] = c["uf"].map(lambda u: UF_COORD[u][0])
    c["longitude"] = c["uf"].map(lambda u: UF_COORD[u][1])
    c["raio"] = (c["obras"] ** 0.5) * 1500  # metros
    return c
