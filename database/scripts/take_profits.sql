-- Table: public.take_profits

-- DROP TABLE IF EXISTS public.take_profits;

CREATE TABLE IF NOT EXISTS public.take_profits
(
    sinal_id integer NOT NULL,
    numero smallint NOT NULL,
    valor real NOT NULL DEFAULT 0,
    quantidade real NOT NULL DEFAULT 0,
    tp_status_id smallint NOT NULL DEFAULT 1,
    proporcao real NOT NULL DEFAULT 1,
    CONSTRAINT pk_take_profits PRIMARY KEY (sinal_id, numero),
    CONSTRAINT fk_sinal FOREIGN KEY (sinal_id)
        REFERENCES public.sinais (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT fk_tp_status FOREIGN KEY (tp_status_id)
        REFERENCES public.take_profit_status (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.take_profits
    OWNER to tradebot;
-- Index: idx_take_profits_sinal

-- DROP INDEX IF EXISTS public.idx_take_profits_sinal;

CREATE INDEX IF NOT EXISTS idx_take_profits_sinal
    ON public.take_profits USING btree
    (sinal_id ASC NULLS LAST, numero ASC NULLS LAST)
    TABLESPACE pg_default;