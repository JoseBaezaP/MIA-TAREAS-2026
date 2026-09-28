"""Pruebas de la vectorización con un vectorizador y un repositorio FALSOS: no gastan tokens
de Voyage ni tocan la base de datos."""

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import pytest
import voyageai.error

from vetrag.ingesta.chunking import Chunk
from vetrag.ingesta.vectorizacion import (
    ResultadoEmbedding,
    armar_lotes,
    con_reintentos,
    ejecutar_vectorizacion,
    leer_chunks,
)

MODELO = "voyage-4"


def chunk(numero: int, tokens: int = 500, fuente: str = "Bib/libro.pdf") -> Chunk:
    texto = "x" * (tokens * 4)
    return Chunk(
        id=f"id{numero}", documento="Libro", fuente=fuente, especialidad="Cirugía",
        idioma="es", ruta_titulos=["Cap 1"], pagina_inicio=1, pagina_fin=1, tokens=tokens,
        texto=texto, texto_para_embedding=texto,
    )  # fmt: skip


class VectorizadorFalso:
    """Devuelve vectores de ceros y reporta 1 token por cada 4 caracteres."""

    modelo = MODELO

    def __init__(self) -> None:
        self.llamadas = 0

    def vectorizar(self, textos: Sequence[str]) -> ResultadoEmbedding:
        self.llamadas += 1
        return ResultadoEmbedding([[0.0] * 1024 for _ in textos], sum(len(t) // 4 for t in textos))


class RepositorioFalso:
    """Guarda en memoria."""

    def __init__(self, tokens_previos: int = 0) -> None:
        self.guardados: dict[str, Sequence[float]] = {}
        self.tokens = tokens_previos

    def ids_existentes(self) -> set[str]:
        return set(self.guardados)

    def tokens_usados(self, modelo: str) -> int:
        return self.tokens

    def guardar(
        self,
        chunks: Sequence[Chunk],
        vectores: Sequence[Sequence[float]],
        tokens: int,
        modelo: str,
    ) -> None:
        self.guardados.update({c.id: v for c, v in zip(chunks, vectores, strict=True)})
        self.tokens += tokens


def test_armar_lotes_respeta_limite_de_textos_y_tokens() -> None:
    chunks = [chunk(i, tokens=500) for i in range(2500)]
    lotes = list(armar_lotes(chunks, max_textos=1000, max_tokens=200_000))
    assert all(len(lote) <= 1000 for lote in lotes)
    assert all(sum(c.tokens for c in lote) <= 200_000 for lote in lotes)
    assert sum(len(lote) for lote in lotes) == 2500  # no se pierde ninguno


def test_vectoriza_y_guarda_todo() -> None:
    repositorio = RepositorioFalso()
    resumen = ejecutar_vectorizacion(
        [chunk(i) for i in range(10)], VectorizadorFalso(), repositorio, limite_tokens=10**9
    )
    assert resumen.vectorizados == 10
    assert len(repositorio.guardados) == 10
    assert resumen.tokens_usados_en_esta_corrida == 10 * 500


def test_reanuda_sin_repetir_chunks() -> None:
    repositorio = RepositorioFalso()
    vectorizador = VectorizadorFalso()
    chunks = [chunk(i) for i in range(10)]
    ejecutar_vectorizacion(chunks[:4], vectorizador, repositorio, limite_tokens=10**9)
    resumen = ejecutar_vectorizacion(chunks, vectorizador, repositorio, limite_tokens=10**9)
    assert resumen.ya_existian == 4
    assert resumen.vectorizados == 6


def test_se_detiene_antes_de_pasar_el_limite() -> None:
    # Ya se usaron 190 millones: no cabe ni un lote más.
    repositorio = RepositorioFalso(tokens_previos=190_000_000)
    vectorizador = VectorizadorFalso()
    resumen = ejecutar_vectorizacion(
        [chunk(i) for i in range(10)], vectorizador, repositorio, limite_tokens=190_000_000
    )
    assert resumen.detenido_por_limite
    assert resumen.vectorizados == 0
    assert vectorizador.llamadas == 0  # ni siquiera se llamó a la API


def test_se_detiene_a_la_mitad_si_se_acerca_al_limite() -> None:
    repositorio = RepositorioFalso()
    chunks = [chunk(i, tokens=500) for i in range(1000)]  # ~500 mil tokens en 3 lotes
    resumen = ejecutar_vectorizacion(
        chunks, VectorizadorFalso(), repositorio, limite_tokens=300_000
    )
    assert resumen.detenido_por_limite
    assert 0 < resumen.vectorizados < 1000
    assert repositorio.tokens <= 300_000


def test_reintenta_errores_temporales() -> None:
    intentos: list[int] = []
    esperas: list[float] = []

    def falla_dos_veces() -> ResultadoEmbedding:
        intentos.append(1)
        if len(intentos) < 3:
            raise voyageai.error.RateLimitError("demasiadas peticiones")
        return ResultadoEmbedding([[0.0]], 1)

    resultado = con_reintentos(falla_dos_veces, espera_inicial=1, dormir=esperas.append)
    assert resultado.tokens == 1
    assert esperas == [1, 2]  # espera creciente


def test_no_reintenta_errores_definitivos() -> None:
    def api_key_invalida() -> ResultadoEmbedding:
        raise voyageai.error.AuthenticationError("API key inválida")

    with pytest.raises(voyageai.error.AuthenticationError):
        con_reintentos(api_key_invalida, dormir=lambda _: None)


def test_leer_chunks_filtra_por_fuente(tmp_path: Path) -> None:
    ruta = tmp_path / "chunks.jsonl"
    ruta.write_text(
        "\n".join(json.dumps(asdict(chunk(i, fuente=f"Bib/libro{i % 2}.pdf"))) for i in range(6)),
        encoding="utf-8",
    )
    assert len(list(leer_chunks(ruta))) == 6
    assert len(list(leer_chunks(ruta, {"Bib/libro0.pdf"}))) == 3
