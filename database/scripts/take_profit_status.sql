-- Table: public.take_profit_status

-- DROP TABLE IF EXISTS public.take_profit_status;

CREATE TABLE IF NOT EXISTS public.take_profit_status
(
    id smallint NOT NULL,
    descricao text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT take_profit_status_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.take_profit_status
    OWNER to tradebot;