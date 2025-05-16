-- Table: public.break_even_status

-- DROP TABLE IF EXISTS public.break_even_status;

CREATE TABLE IF NOT EXISTS public.break_even_status
(
    id smallint NOT NULL,
    descricao text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT break_even_status_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.break_even_status
    OWNER to tradebot;