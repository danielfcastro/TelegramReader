CREATE TABLE IF NOT EXISTS public.sinais
(
    id integer NOT NULL DEFAULT nextval('sinais_id_seq'::regclass),
    data_hora timestamp without time zone NOT NULL,
    par text COLLATE pg_catalog."default" NOT NULL,
    tipo_ordem text COLLATE pg_catalog."default" NOT NULL,
    margem text COLLATE pg_catalog."default" NOT NULL,
    alavancagem text COLLATE pg_catalog."default" NOT NULL,
    sl real NOT NULL,
    ordem_status_id smallint NOT NULL DEFAULT 0,
    break_even_status_id smallint NOT NULL DEFAULT 0,
    order_id bigint DEFAULT 0,
    entry_price real DEFAULT 0,
    quantidade real NOT NULL DEFAULT 0,
    janela_5min timestamp without time zone GENERATED ALWAYS AS ((date_trunc('minute'::text, data_hora) - ('00:01:00'::interval * (((EXTRACT(minute FROM data_hora))::integer % 5))::double precision))) STORED,
    CONSTRAINT sinais_pkey PRIMARY KEY (id),
    CONSTRAINT fk_break_even_status FOREIGN KEY (break_even_status_id)
        REFERENCES public.break_even_status (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT fk_ordem_status FOREIGN KEY (ordem_status_id)
        REFERENCES public.ordem_status (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.sinais
    OWNER to tradebot;

CREATE INDEX IF NOT EXISTS idx_sinais_par_status
    ON public.sinais USING btree
    (par COLLATE pg_catalog."default" ASC NULLS LAST, ordem_status_id ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE UNIQUE INDEX IF NOT EXISTS unique_par_janela
    ON public.sinais USING btree
    (par COLLATE pg_catalog."default" ASC NULLS LAST, janela_5min ASC NULLS LAST)
    TABLESPACE pg_default;