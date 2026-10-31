-- =====================================================================
-- Mapa das obras brasileiras (Ancine) - Esquema normalizado (3FN)
-- SGBD: MariaDB 10.2+  |  Charset: utf8mb4
-- Pode ser executado mais de uma vez (CREATE ... IF NOT EXISTS).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS mapa_obras
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE mapa_obras;

-- ---------------------------------------------------------------------
-- 1) TABELAS DE DOMINIO (listas de valores repetidos)
--    Collation _ci: comparacao sem diferenciar maiuscula/acento,
--    o que ja evita duplicatas como "FRANCA" e "FRANÇA".
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tipo_obra (
  id_tipo_obra SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome         VARCHAR(120)      NOT NULL,
  PRIMARY KEY (id_tipo_obra),
  UNIQUE KEY uq_tipo_obra_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS subtipo_obra (
  id_subtipo_obra SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(120)      NOT NULL,
  PRIMARY KEY (id_subtipo_obra),
  UNIQUE KEY uq_subtipo_obra_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS classificacao (
  id_classificacao SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome             VARCHAR(120)      NOT NULL,
  PRIMARY KEY (id_classificacao),
  UNIQUE KEY uq_classificacao_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS organizacao_temporal (
  id_organizacao_temporal SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome                    VARCHAR(50)       NOT NULL,
  PRIMARY KEY (id_organizacao_temporal),
  UNIQUE KEY uq_organizacao_temporal_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS segmento (
  id_segmento SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome        VARCHAR(120)      NOT NULL,
  PRIMARY KEY (id_segmento),
  UNIQUE KEY uq_segmento_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pais (
  id_pais SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome    VARCHAR(60)       NOT NULL,
  PRIMARY KEY (id_pais),
  UNIQUE KEY uq_pais_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uf (
  id_uf TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sigla CHAR(2)          NOT NULL,
  PRIMARY KEY (id_uf),
  UNIQUE KEY uq_uf_sigla (sigla)
) ENGINE=InnoDB;

-- O mesmo nome de cidade pode existir em estados diferentes,
-- por isso a unicidade e (nome + uf).
CREATE TABLE IF NOT EXISTS municipio (
  id_municipio INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome         VARCHAR(60)      NOT NULL,
  id_uf        TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (id_municipio),
  UNIQUE KEY uq_municipio_nome_uf (nome, id_uf),
  CONSTRAINT fk_municipio_uf FOREIGN KEY (id_uf) REFERENCES uf (id_uf)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2) ENTIDADES
--    CNPJ guardado so com os 14 digitos (sem pontuacao).
--    chave_sem_cnpj: identifica quem NAO tem CNPJ (pessoa fisica / nao
--    informado) por nome + local. O ETL preenche so para esses; para
--    quem tem CNPJ fica NULL, e o UNIQUE ignora NULL.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS requerente (
  id_requerente INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo_pessoa   ENUM('PJ','PF') NOT NULL,
  cnpj          CHAR(14)     NULL,
  nome          VARCHAR(150) NOT NULL,
  id_municipio  INT UNSIGNED NOT NULL,
  chave_sem_cnpj VARCHAR(170) NULL,   -- ETL preenche (nome|id_municipio) so se cnpj for NULL
  PRIMARY KEY (id_requerente),
  UNIQUE KEY uq_requerente_cnpj (cnpj),
  UNIQUE KEY uq_requerente_sem_cnpj (chave_sem_cnpj),
  CONSTRAINT fk_requerente_municipio FOREIGN KEY (id_municipio)
    REFERENCES municipio (id_municipio),
  CONSTRAINT ck_requerente_pessoa CHECK (
    (tipo_pessoa = 'PJ' AND cnpj IS NOT NULL) OR
    (tipo_pessoa = 'PF' AND cnpj IS NULL))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS produtor (
  id_produtor  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo_pessoa  ENUM('PJ','PF','NAO_INFORMADO') NOT NULL,
  cnpj         CHAR(14)     NULL,
  nome         VARCHAR(150) NOT NULL,          -- nome canonico (o mais frequente)
  id_pais      SMALLINT UNSIGNED NULL,
  chave_sem_cnpj VARCHAR(170) NULL,   -- ETL preenche (nome|id_pais) so se cnpj for NULL
  PRIMARY KEY (id_produtor),
  UNIQUE KEY uq_produtor_cnpj (cnpj),
  UNIQUE KEY uq_produtor_sem_cnpj (chave_sem_cnpj),
  CONSTRAINT fk_produtor_pais FOREIGN KEY (id_pais) REFERENCES pais (id_pais),
  CONSTRAINT ck_produtor_pessoa CHECK (
    (tipo_pessoa = 'PJ' AND cnpj IS NOT NULL) OR
    (tipo_pessoa <> 'PJ' AND cnpj IS NULL))
) ENGINE=InnoDB;

-- Sinonimos: outros nomes encontrados para o mesmo produtor (mesmo CNPJ)
CREATE TABLE IF NOT EXISTS produtor_nome_alternativo (
  id_nome_alternativo INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_produtor         INT UNSIGNED NOT NULL,
  nome                VARCHAR(150) NOT NULL,
  PRIMARY KEY (id_nome_alternativo),
  UNIQUE KEY uq_produtor_nome_alt (id_produtor, nome),
  CONSTRAINT fk_nome_alt_produtor FOREIGN KEY (id_produtor)
    REFERENCES produtor (id_produtor) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3) OBRA (chave = CPB, unico na base original)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS obra (
  cpb                      CHAR(14)      NOT NULL,
  titulo                   VARCHAR(100)  NOT NULL,
  data_emissao             DATE          NOT NULL,
  situacao                 VARCHAR(20)   NOT NULL,   -- DEFERIDO / DEFERIDO_SUS
  id_tipo_obra             SMALLINT UNSIGNED NOT NULL,
  id_subtipo_obra          SMALLINT UNSIGNED NULL,
  id_classificacao         SMALLINT UNSIGNED NOT NULL,
  id_organizacao_temporal  SMALLINT UNSIGNED NOT NULL,
  id_segmento              SMALLINT UNSIGNED NOT NULL,
  duracao_minutos          DECIMAL(10,2) NOT NULL,
  qtd_episodios            INT UNSIGNED  NULL,
  ano_prod_inicial         SMALLINT UNSIGNED NULL,
  ano_prod_final           SMALLINT UNSIGNED NULL,
  coproducao_internacional BOOLEAN       NOT NULL,
  id_requerente            INT UNSIGNED  NOT NULL,
  PRIMARY KEY (cpb),
  KEY ix_obra_data_emissao (data_emissao),
  CONSTRAINT fk_obra_tipo FOREIGN KEY (id_tipo_obra)
    REFERENCES tipo_obra (id_tipo_obra),
  CONSTRAINT fk_obra_subtipo FOREIGN KEY (id_subtipo_obra)
    REFERENCES subtipo_obra (id_subtipo_obra),
  CONSTRAINT fk_obra_classificacao FOREIGN KEY (id_classificacao)
    REFERENCES classificacao (id_classificacao),
  CONSTRAINT fk_obra_org_temporal FOREIGN KEY (id_organizacao_temporal)
    REFERENCES organizacao_temporal (id_organizacao_temporal),
  CONSTRAINT fk_obra_segmento FOREIGN KEY (id_segmento)
    REFERENCES segmento (id_segmento),
  CONSTRAINT fk_obra_requerente FOREIGN KEY (id_requerente)
    REFERENCES requerente (id_requerente),
  CONSTRAINT ck_obra_cpb CHECK (cpb REGEXP '^B[0-9]{13}$'),
  CONSTRAINT ck_obra_duracao CHECK (duracao_minutos >= 0),
  CONSTRAINT ck_obra_anos CHECK (
    ano_prod_final IS NULL OR ano_prod_inicial IS NULL
    OR ano_prod_final >= ano_prod_inicial)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4) RELACAO N:N obra <-> produtor
--    PK composta: impede o mesmo par repetido.
--    Obras sem produtor (801) simplesmente nao tem linhas aqui.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS obra_produtor (
  cpb         CHAR(14)     NOT NULL,
  id_produtor INT UNSIGNED NOT NULL,
  PRIMARY KEY (cpb, id_produtor),
  KEY ix_obra_produtor_produtor (id_produtor),
  CONSTRAINT fk_op_obra FOREIGN KEY (cpb)
    REFERENCES obra (cpb) ON DELETE CASCADE,
  CONSTRAINT fk_op_produtor FOREIGN KEY (id_produtor)
    REFERENCES produtor (id_produtor)
) ENGINE=InnoDB;
