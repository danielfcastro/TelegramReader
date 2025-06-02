--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8
-- Dumped by pg_dump version 17.4

-- Started on 2025-06-02 14:29:13

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
-- TOC entry 3150 (class 1262 OID 16385)
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
-- TOC entry 3140 (class 0 OID 32987)
-- Dependencies: 222
-- Data for Name: break_even_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.break_even_status VALUES (0, 'INATIVO') ON CONFLICT DO NOTHING;
INSERT INTO v2.break_even_status VALUES (1, 'AGUARDANDO BREAK EVEN') ON CONFLICT DO NOTHING;
INSERT INTO v2.break_even_status VALUES (2, 'BREAK EVEN AJUSTADO') ON CONFLICT DO NOTHING;


--
-- TOC entry 3142 (class 0 OID 33001)
-- Dependencies: 224
-- Data for Name: ordem; Type: TABLE DATA; Schema: v2; Owner: tradebot
--



--
-- TOC entry 3141 (class 0 OID 32994)
-- Dependencies: 223
-- Data for Name: ordem_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.ordem_status VALUES (1, 'ENVIADA PARA CORRETORA') ON CONFLICT DO NOTHING;
INSERT INTO v2.ordem_status VALUES (2, 'CONCLUÍDA') ON CONFLICT DO NOTHING;
INSERT INTO v2.ordem_status VALUES (3, 'IGNORADA') ON CONFLICT DO NOTHING;


--
-- TOC entry 3143 (class 0 OID 33027)
-- Dependencies: 225
-- Data for Name: take_profit_status; Type: TABLE DATA; Schema: v2; Owner: tradebot
--

INSERT INTO v2.take_profit_status VALUES (1, 'CONFIGURADO') ON CONFLICT DO NOTHING;
INSERT INTO v2.take_profit_status VALUES (2, 'ATINGIDO') ON CONFLICT DO NOTHING;


--
-- TOC entry 3144 (class 0 OID 33054)
-- Dependencies: 226
-- Data for Name: take_profits; Type: TABLE DATA; Schema: v2; Owner: tradebot
--



--
-- TOC entry 2981 (class 2606 OID 32993)
-- Name: break_even_status break_even_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.break_even_status
    ADD CONSTRAINT break_even_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2993 (class 2606 OID 33062)
-- Name: take_profits pk_take_profits; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profits
    ADD CONSTRAINT pk_take_profits PRIMARY KEY (order_id, numero);


--
-- TOC entry 2986 (class 2606 OID 33014)
-- Name: ordem sinais_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT sinais_pkey PRIMARY KEY (id);


--
-- TOC entry 2990 (class 2606 OID 33033)
-- Name: take_profit_status take_profit_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profit_status
    ADD CONSTRAINT take_profit_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2983 (class 2606 OID 33000)
-- Name: ordem_status trailing_stop_status_pkey; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem_status
    ADD CONSTRAINT trailing_stop_status_pkey PRIMARY KEY (id);


--
-- TOC entry 2988 (class 2606 OID 33053)
-- Name: ordem unique_order_id; Type: CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT unique_order_id UNIQUE (order_id);


--
-- TOC entry 2984 (class 1259 OID 33025)
-- Name: idx_sinais_par_status; Type: INDEX; Schema: v2; Owner: tradebot
--

CREATE INDEX idx_sinais_par_status ON v2.ordem USING btree (symbol, ordem_status_id);


--
-- TOC entry 2991 (class 1259 OID 33068)
-- Name: idx_take_profits_order; Type: INDEX; Schema: v2; Owner: tradebot
--

CREATE INDEX idx_take_profits_order ON v2.take_profits USING btree (order_id, numero);


--
-- TOC entry 2994 (class 2606 OID 33015)
-- Name: ordem fk_break_even_status; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT fk_break_even_status FOREIGN KEY (break_even_status_id) REFERENCES v2.break_even_status(id);


--
-- TOC entry 2995 (class 2606 OID 33020)
-- Name: ordem fk_ordem_status; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.ordem
    ADD CONSTRAINT fk_ordem_status FOREIGN KEY (ordem_status_id) REFERENCES v2.ordem_status(id);


--
-- TOC entry 2996 (class 2606 OID 33063)
-- Name: take_profits take_profits_order_id_fkey; Type: FK CONSTRAINT; Schema: v2; Owner: tradebot
--

ALTER TABLE ONLY v2.take_profits
    ADD CONSTRAINT take_profits_order_id_fkey FOREIGN KEY (order_id) REFERENCES v2.ordem(order_id) ON DELETE CASCADE;


--
-- TOC entry 3151 (class 0 OID 0)
-- Dependencies: 3150
-- Name: DATABASE tradebotdb; Type: ACL; Schema: -; Owner: postgres
--

GRANT ALL ON DATABASE tradebotdb TO tradebot;


-- Completed on 2025-06-02 14:29:14

--
-- PostgreSQL database dump complete
--

