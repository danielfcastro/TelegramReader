--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8
-- Dumped by pg_dump version 17.4

-- Started on 2025-06-02 18:17:00

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE IF EXISTS tradebotdb;
--
-- TOC entry 3155 (class 1262 OID 16385)
-- Name: tradebotdb; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE tradebotdb WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = icu LC_COLLATE = 'C' LC_CTYPE = 'C.UTF-8' ICU_LOCALE = 'en-001-x-icu';


ALTER DATABASE tradebotdb OWNER TO postgres;

\connect tradebotdb

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 6 (class 2615 OID 32986)
-- Name: v2; Type: SCHEMA; Schema: -; Owner: tradebot
--

CREATE SCHEMA v2;


ALTER SCHEMA v2 OWNER TO tradebot;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 222 (class 1259 OID 32987)
-- Name: break_even_status; Type: TABLE; Schema: v2; Owner: tradebot
--

CREATE TABLE v2.break_even_status (
    id smallint NOT NULL,
    descricao text NOT NULL
);


ALTER TABLE v2.break_even_status OWNER TO tradebot;

--
-- TOC entry 224 (class 1259 OID 33001)
-- Name: ordem; Type: TABLE; Schema: v2; Owner: tradebot
--

CREATE TABLE v2.ordem (
    id integer DEFAULT nextval('public.sinais_id_seq'::regclass) NOT NULL,
    data_hora timestamp without time zone NOT NULL,
    symbol text NOT NULL,
    tipo_ordem text NOT NULL,
    margem text NOT NULL,
    alavancagem text NOT NULL,
    sl real NOT NULL,
    ordem_status_id smallint DEFAULT 0 NOT NULL,
    break_even_status_id smallint DEFAULT 0 NOT NULL,
    order_id bigint DEFAULT 0 NOT NULL,
    entry_price real DEFAULT 0,
    quantidade real DEFAULT 0 NOT NULL
);


ALTER TABLE v2.ordem OWNER TO tradebot;

--
-- TOC entry 3158 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.id IS 'Identificador interno da ordem.';


--
-- TOC entry 3159 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.data_hora; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.data_hora IS 'Momento em que a ordem foi criada.';


--
-- TOC entry 3160 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.symbol; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.symbol IS 'Par de negociação (ex: BTC-USDT).';


--
-- TOC entry 3161 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.tipo_ordem; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.tipo_ordem IS 'Direção da ordem (BUY / SELL).';


--
-- TOC entry 3162 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.margem; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.margem IS 'Tipo de margem (ex: Cross).';


--
-- TOC entry 3163 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.alavancagem; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.alavancagem IS 'Alavancagem usada (ex: 20X).';


--
-- TOC entry 3164 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.sl; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.sl IS 'Stop loss da ordem.';


--
-- TOC entry 3165 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.ordem_status_id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.ordem_status_id IS 'Status geral da ordem (FK para ordem_status).';


--
-- TOC entry 3166 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.break_even_status_id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.break_even_status_id IS 'Status do break even (FK para break_even_status).';


--
-- TOC entry 3167 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.order_id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.order_id IS 'ID da ordem na corretora (único).';


--
-- TOC entry 3168 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.entry_price; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.entry_price IS 'Preço de entrada efetivo.';


--
-- TOC entry 3169 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN ordem.quantidade; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.ordem.quantidade IS 'Quantidade total da ordem.';


--
-- TOC entry 223 (class 1259 OID 32994)
-- Name: ordem_status; Type: TABLE; Schema: v2; Owner: tradebot
--

CREATE TABLE v2.ordem_status (
    id smallint NOT NULL,
    descricao text NOT NULL
);


ALTER TABLE v2.ordem_status OWNER TO tradebot;

--
-- TOC entry 225 (class 1259 OID 33027)
-- Name: take_profit_status; Type: TABLE; Schema: v2; Owner: tradebot
--

CREATE TABLE v2.take_profit_status (
    id smallint NOT NULL,
    descricao text NOT NULL
);


ALTER TABLE v2.take_profit_status OWNER TO tradebot;

--
-- TOC entry 226 (class 1259 OID 33054)
-- Name: take_profits; Type: TABLE; Schema: v2; Owner: tradebot
--

CREATE TABLE v2.take_profits (
    order_id bigint NOT NULL,
    numero smallint NOT NULL,
    valor real DEFAULT 0 NOT NULL,
    quantidade real DEFAULT 0 NOT NULL,
    tp_status_id smallint DEFAULT 1 NOT NULL,
    proporcao real DEFAULT 1 NOT NULL
);


ALTER TABLE v2.take_profits OWNER TO tradebot;

--
-- TOC entry 3170 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.order_id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.order_id IS 'ID da ordem principal (FK para v2.ordem).';


--
-- TOC entry 3171 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.numero; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.numero IS 'Número do TP (1 a 4).';


--
-- TOC entry 3172 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.valor; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.valor IS 'Valor de disparo do Take Profit.';


--
-- TOC entry 3173 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.quantidade; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.quantidade IS 'Quantidade associada a este TP.';


--
-- TOC entry 3174 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.tp_status_id; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.tp_status_id IS 'Status do TP (FK para take_profit_status).';


--
-- TOC entry 3175 (class 0 OID 0)
-- Dependencies: 226
-- Name: COLUMN take_profits.proporcao; Type: COMMENT; Schema: v2; Owner: tradebot
--

COMMENT ON COLUMN v2.take_profits.proporcao IS 'Proporção da posição total associada a este TP.';


--
-- TOC entry 3145 (class 0 OID 32987)
-- Dependencies: 222
-- Data for Name: break_even_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.break_even_status VALUES (0, 'INATIVO') ON CONFLICT DO NOTHING;
INSERT INTO v2.break_even_status VALUES (1, 'AGUARDANDO BREAK EVEN') ON CONFLICT DO NOTHING;
INSERT INTO v2.break_even_status VALUES (2, 'BREAK EVEN AJUSTADO') ON CONFLICT DO NOTHING;


--
-- TOC entry 3147 (class 0 OID 33001)
-- Dependencies: 224
-- Data for Name: ordem; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.ordem VALUES (347, '2025-06-02 16:39:33.371311', 'ICX-USDT', 'SELL', 'Cross', '20X', 0.13497, 2, 1, 1929578460836007936, 0.1225, 23912.656) ON CONFLICT DO NOTHING;
INSERT INTO v2.ordem VALUES (348, '2025-06-02 16:43:37.334022', 'SANTOS-USDT', 'SELL', 'Cross', '20X', 2.5784, 2, 1, 1929579634796531712, 2.332, 1251.3772) ON CONFLICT DO NOTHING;


--
-- TOC entry 3146 (class 0 OID 32994)
-- Dependencies: 223
-- Data for Name: ordem_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.ordem_status VALUES (1, 'ENVIADA PARA CORRETORA') ON CONFLICT DO NOTHING;
INSERT INTO v2.ordem_status VALUES (2, 'CONCLUÍDA') ON CONFLICT DO NOTHING;
INSERT INTO v2.ordem_status VALUES (3, 'IGNORADA') ON CONFLICT DO NOTHING;


--
-- TOC entry 3148 (class 0 OID 33027)
-- Dependencies: 225
-- Data for Name: take_profit_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.take_profit_status VALUES (1, 'CONFIGURADO') ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profit_status VALUES (2, 'ATINGIDO') ON CONFLICT DO NOTHING;


--
-- TOC entry 3149 (class 0 OID 33054)
-- Dependencies: 226
-- Data for Name: take_profits; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.take_profits VALUES (1929578460836007936, 1, 0.12147, 2391.2656, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929578460836007936, 2, 0.12025, 4782.5312, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929578460836007936, 3, 0.11902, 11956.328, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929578460836007936, 4, 0.11657, 4782.5312, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929579634796531712, 1, 2.32056, 125.1377, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929579634796531712, 2, 2.29712, 250.2754, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929579634796531712, 3, 2.27368, 625.6885, 1, 1) ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profits VALUES (1929579634796531712, 4, 2.2268, 250.2754, 1, 1) ON CONFLICT DO NOTHING;


--
-- TOC entry 2986 (class 2606 OID 32993)
-- Name: break_even_status break_even_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.break_even_status
    ADD CONSTRAINT break_even_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2998 (class 2606 OID 33062)
-- Name: take_profits pk_take_profits; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profits
    ADD CONSTRAINT pk_take_profits PRIMARY KEY (order_id, numero);


--
-- TOC entry 2991 (class 2606 OID 33014)
-- Name: ordem sinais_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT sinais_pkey PRIMARY KEY (id);


--
-- TOC entry 2995 (class 2606 OID 33033)
-- Name: take_profit_status take_profit_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profit_status
    ADD CONSTRAINT take_profit_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2988 (class 2606 OID 33000)
-- Name: ordem_status trailing_stop_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem_status
    ADD CONSTRAINT trailing_stop_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2993 (class 2606 OID 33053)
-- Name: ordem unique_order_id; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT unique_order_id UNIQUE (order_id);


--
-- TOC entry 2989 (class 1259 OID 33025)
-- Name: idx_sinais_par_status; Type: INDEX; Schema: v2; Owner: tradebot
--

CREATE INDEX idx_sinais_par_status ON v2.ordem USING btree (symbol, ordem_status_id);


--
-- TOC entry 2996 (class 1259 OID 33068)
-- Name: idx_take_profits_order; Type: INDEX; Schema: v2; Owner: tradebot
--

CREATE INDEX idx_take_profits_order ON v2.take_profits USING btree (order_id, numero);


--
-- TOC entry 2999 (class 2606 OID 33015)
-- Name: ordem fk_break_even_status; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT fk_break_even_status FOREIGN KEY (break_even_status_id) REFERENCES v2.break_even_status(id);


--
-- TOC entry 3000 (class 2606 OID 33020)
-- Name: ordem fk_ordem_status; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT fk_ordem_status FOREIGN KEY (ordem_status_id) REFERENCES v2.ordem_status(id);


--
-- TOC entry 3001 (class 2606 OID 33063)
-- Name: take_profits take_profits_order_id_fkey; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profits
    ADD CONSTRAINT take_profits_order_id_fkey FOREIGN KEY (order_id) REFERENCES v2.ordem(order_id) ON DELETE CASCADE;


--
-- TOC entry 3156 (class 0 OID 0)
-- Dependencies: 3155
-- Name: DATABASE tradebotdb; Type: ACL; Schema: -; Owner: postgres
--

GRANT ALL ON DATABASE tradebotdb TO tradebot;


--
-- TOC entry 3157 (class 0 OID 0)
-- Dependencies: 6
-- Name: SCHEMA v2; Type: ACL; Schema: -; Owner: tradebot
--

GRANT USAGE ON SCHEMA v2 TO PUBLIC;


-- Completed on 2025-06-02 18:17:00

--
-- PostgreSQL database dump complete
--

