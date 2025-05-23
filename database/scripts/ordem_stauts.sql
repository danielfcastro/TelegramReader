-- Table: public.ordem_status

-- DROP TABLE IF EXISTS public.ordem_status;

CREATE TABLE IF NOT EXISTS public.ordem_status
(
    id smallint NOT NULL,
    descricao text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT trailing_stop_status_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.ordem_status
    OWNER to tradebot;