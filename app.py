"""Dashboard Streamlit - Mapa das obras brasileiras (Ancine, 2020 a 2026).

Rodar:
  export DB_PASSWORD='senha_do_etl_obras'
  streamlit run app.py
Variaveis opcionais: DB_HOST, DB_PORT, DB_USER, DB_NAME (mesmos padroes do etl.py).
"""
import os

import plotly.express as px
import pymysql
import streamlit as st

import dados

st.set_page_config(page_title="Mapa das obras brasileiras", layout="wide")


@st.cache_data(show_spinner="Carregando dados do banco...", ttl=3600)
def carregar_dados():
    con = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "etl_obras"),
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "mapa_obras"),
        charset="utf8mb4",
    )
    try:
        return dados.carregar(con)
    finally:
        con.close()


def barras_h(df, y, titulo):
    fig = px.bar(df, x="obras", y=y, orientation="h", title=titulo, text="obras")
    fig.update_layout(yaxis={"categoryorder": "total ascending", "title": None},
                      xaxis={"title": "Obras"}, margin={"t": 50, "l": 0, "r": 10, "b": 0})
    return fig


# ------------------------------------------------------------------ dados
if "DB_PASSWORD" not in os.environ:
    st.error("Defina a senha do banco antes de abrir o app: "
             "`export DB_PASSWORD='sua_senha'` e rode `streamlit run app.py` de novo.")
    st.stop()

obras, op = carregar_dados()

# ---------------------------------------------------------------- filtros
st.sidebar.header("Filtros")
anos = sorted(obras["ano"].unique())
ano_ini, ano_fim = st.sidebar.select_slider("Ano de emissão do CPB", options=anos,
                                            value=(anos[0], anos[-1]))
tipos = st.sidebar.multiselect("Tipo de obra", sorted(obras["tipo"].unique()),
                               default=sorted(obras["tipo"].unique()))
ufs = st.sidebar.multiselect("UF do requerente", sorted(obras["uf"].unique()),
                             default=sorted(obras["uf"].unique()))
st.sidebar.caption(f"Dados até {obras['data_emissao'].max():%d/%m/%Y} "
                   f"(o ano mais recente está incompleto).")

f = obras[obras["ano"].between(ano_ini, ano_fim) & obras["tipo"].isin(tipos) & obras["uf"].isin(ufs)]
op_f = op[op["cpb"].isin(f["cpb"])]

st.title("Mapa das obras audiovisuais brasileiras")
st.caption("Obras não publicitárias com CPB emitido pela Ancine · bases abertas da Ancine")

if f.empty:
    st.warning("Nenhuma obra para os filtros escolhidos.")
    st.stop()

# -------------------------------------------------------------------- KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Obras", f"{len(f):,}".replace(",", "."))
k2.metric("Requerentes", f"{f['id_requerente'].nunique():,}".replace(",", "."))
k3.metric("Produtores identificados",
          f"{op_f.loc[op_f['tipo_pessoa'] != 'NAO_INFORMADO', 'id_produtor'].nunique():,}".replace(",", "."))
k4.metric("Coproduções internacionais", f"{(f['coprod'] == 'Sim').mean():.1%}".replace(".", ","))

# ------------------------------------------------------------ evolucao/tipo
c1, c2 = st.columns(2)
with c1:
    fig = px.line(dados.obras_por_ano(f), x="ano", y="obras", markers=True,
                  title="Obras por ano de emissão do CPB")
    fig.update_layout(xaxis={"dtick": 1, "title": "Ano"}, yaxis={"title": "Obras"},
                      margin={"t": 50, "l": 0, "r": 10, "b": 0})
    st.plotly_chart(fig)
with c2:
    st.plotly_chart(barras_h(dados.contagem(f, "tipo", rotulo="Tipo"), "Tipo", "Obras por tipo"))

# ---------------------------------------------------------------- segmento
c3, c4 = st.columns(2)
with c3:
    st.plotly_chart(barras_h(dados.contagem(f, "segmento", rotulo="Segmento"), "Segmento",
                             "Obras por segmento de destinação inicial"))
with c4:
    cp = dados.contagem(f, "coprod", rotulo="Coprodução internacional")
    fig = px.pie(cp, names="Coprodução internacional", values="obras", hole=0.5,
                 title="Coprodução internacional")
    fig.update_layout(margin={"t": 50, "l": 0, "r": 0, "b": 0})
    st.plotly_chart(fig)

# --------------------------------------------------------------------- UF
st.subheader("Obras por UF do requerente")
u1, u2 = st.columns(2)
uf_df = dados.mapa_uf(f)
with u1:
    fig = px.bar(uf_df, x="uf", y="obras", text="obras")
    fig.update_layout(xaxis={"categoryorder": "total descending", "title": "UF"},
                      yaxis={"title": "Obras"}, margin={"t": 20, "l": 0, "r": 10, "b": 0})
    st.plotly_chart(fig)
with u2:
    st.map(uf_df, latitude="latitude", longitude="longitude", size="raio")
    st.caption("Cada bolha fica sobre a capital da UF; o tamanho é proporcional à "
               "raiz do número de obras.")

# ---------------------------------------------------------------- rankings
st.subheader("Rankings")
r1, r2 = st.columns(2)
with r1:
    st.plotly_chart(barras_h(dados.ranking_produtores(op_f), "produtor", "Top 10 produtores"))
    st.caption("Ignora produtores com identificação 'não informado'. "
               "Obras sem produtor na base não entram neste ranking.")
with r2:
    st.plotly_chart(barras_h(dados.ranking_requerentes(f), "requerente", "Top 10 requerentes"))

with st.expander("Ver tabela de obras filtradas"):
    st.dataframe(f[["cpb", "titulo", "data_emissao", "tipo", "segmento", "uf", "requerente"]])
