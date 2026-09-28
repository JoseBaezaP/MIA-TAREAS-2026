-- Esquema de la base de conocimiento (se aplica con `uv run vetrag-ingesta vectorizar`).
-- Solo estructura: los DATOS nunca se suben al repositorio (contienen texto de los libros).

CREATE EXTENSION IF NOT EXISTS vector;

-- Un fragmento de un documento con su vector (voyage-4: 1024 dimensiones).
CREATE TABLE IF NOT EXISTS chunks (
    id                text PRIMARY KEY,
    documento         text NOT NULL,
    fuente            text NOT NULL,
    especialidad      text NOT NULL DEFAULT '',
    idioma            text NOT NULL DEFAULT 'desconocido',
    ruta_titulos      text[] NOT NULL DEFAULT '{}',
    pagina_inicio     integer,
    pagina_fin        integer,
    tokens            integer NOT NULL,
    texto             text NOT NULL,
    unidades_dudosas  text[] NOT NULL DEFAULT '{}',
    embedding         vector(1024) NOT NULL,
    modelo_embedding  text NOT NULL,
    creado_en         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_especialidad_idx ON chunks (especialidad);
CREATE INDEX IF NOT EXISTS chunks_fuente_idx ON chunks (fuente);

-- Registro de cada llamada a Voyage: los tokens que REPORTA la API (no una estimación),
-- para no pasar del límite de tokens gratuitos aunque el proceso se interrumpa y se reanude.
CREATE TABLE IF NOT EXISTS uso_voyage (
    id         bigserial PRIMARY KEY,
    modelo     text NOT NULL,
    chunks     integer NOT NULL,
    tokens     integer NOT NULL,
    creado_en  timestamptz NOT NULL DEFAULT now()
);
