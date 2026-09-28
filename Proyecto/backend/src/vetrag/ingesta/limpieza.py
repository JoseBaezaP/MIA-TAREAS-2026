"""Paso 3 de la F2: limpieza del Markdown antes de dividirlo en chunks.

Cuatro tareas, cada una con su función pura:

1. Quitar encabezados y pies de página repetidos (``quitar_lineas_repetidas``).
2. Quitar datos personales: nombres junto a etiquetas, matrículas, teléfonos y correos
   (``quitar_datos_personales``). No hay regla de direcciones a propósito: "Col." o "colonia"
   aparecen en textos de bacteriología y el riesgo de borrar contenido es mayor que el
   beneficio.
3. Corregir ``µg`` mal leído por el OCR y reportar unidades que no están en el catálogo
   de ``unidades.py`` (``corregir_unidades``).
4. Quitar números de página sueltos y espacios de más (``quitar_numeros_pagina``).

Cada cambio queda registrado como un ``Cambio`` para el reporte de revisión.
"""

import csv
import logging
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
from pathlib import Path

from vetrag.ingesta.conversion import MARCA_PAGINA, PATRON_MARCA_PAGINA, ruta_markdown
from vetrag.ingesta.seleccion import DocumentoSeleccionado
from vetrag.ingesta.unidades import (
    buscar_unidades_desconocidas,
    corregir_confusiones_ocr,
    tiene_contexto_de_dosis,
)

logger = logging.getLogger(__name__)

MARCA_DATO_PERSONAL = "[dato personal eliminado]"

# --- Líneas repetidas -----------------------------------------------------------------
PROPORCION_MIN_REPETIDA = 0.5  # aparece en la mitad o más de las páginas
MIN_PAGINAS_PARA_REPETIDAS = 5  # con menos páginas, 2 iguales ya serían el 50 %

# --- Números de página ----------------------------------------------------------------
_PATRON_NUMERO_PAGINA = re.compile(
    r"^\s*[-–—]?\s*(p[aá]g(ina)?\.?\s*)?\d{1,4}(\s*(de|/)\s*\d{1,4})?\s*[-–—]?\s*$",  # noqa: RUF001
    re.IGNORECASE,
)

# --- Datos personales -----------------------------------------------------------------
_MAYUSCULA = "A-ZÁÉÍÓÚÑÜ"
_MINUSCULA = "a-záéíóúñü"
_PALABRA_NOMBRE = rf"[{_MAYUSCULA}][{_MINUSCULA}]+"

# "Nombre: …", "Matrícula: …": se elimina la etiqueta y **solo su valor**, que termina en la
# siguiente etiqueta ("Especie:"), coma, celda de tabla o fin de línea. Así, en un caso clínico
# ("Nombre: Mimo Especie: Felina Raza: Persa Edad: 7 años") se conservan los datos clínicos.
# - La etiqueta debe ir al inicio de la línea, de una celda ("**Nombre:", "|Nombre:") o después
#   de una coma: así no se borra "…conocida con el nombre: fibrosis hepatoportal".
# - "nombres" (plural) no cuenta: "Otros nombres: Bobtail Japonés" describe razas de perro.
# - "Paciente:" no está a propósito: en veterinaria describe al animal (dato clínico).
_PATRON_ETIQUETA_PERSONAL = re.compile(
    r"(?:^\s*|(?<=[|*•])|(?<=[,;]\s))"
    r"(nombre|matr[ií]cula|alumn[oa]s?|estudiantes?|propietari[oa]s?"
    r"|t[eé]cnico de lab(oratorio)?\.?)\s*:\s*"
    r"[^|*,;\n]*?[^\s|*,;]"  # el valor
    rf"(?=\s+[{_MAYUSCULA}][{_MINUSCULA}]+\s*:|\s*[|*,;]|\s*$)",  # dónde termina
    re.IGNORECASE,
)
# Línea que abre una lista de personas: "Equipo:", "Integrantes"
_PATRON_INICIO_EQUIPO = re.compile(r"^\W*(equipo|integrantes)\s*:?\s*\W*$", re.IGNORECASE)
# Línea que es solo un nombre (2 a 5 palabras con mayúscula), opcionalmente con matrícula.
_PATRON_LINEA_NOMBRE = re.compile(
    rf"^[\s\-*•]*{_PALABRA_NOMBRE}(\s+{_PALABRA_NOMBRE}){{1,4}}(\s+\d{{6,8}})?\s*$"
)
# Nombre + matrícula en su propia línea, aunque no haya "Equipo:" antes.
_PATRON_NOMBRE_CON_MATRICULA = re.compile(
    rf"^[\s\-*•]*{_PALABRA_NOMBRE}(\s+{_PALABRA_NOMBRE}){{1,4}}\s+\d{{6,8}}\s*$"
)
_PATRON_TELEFONO_ETIQUETA = re.compile(
    r"\b(tel[eé]fonos?|tel|cel(ular)?)\.?\s*:?\s*\+?[\d()][\d\s().-]{6,}\d", re.IGNORECASE
)
# Teléfono sin etiqueta. Se excluyen rangos de años, "(250) 1996-1998", que aparecen en las
# referencias bibliográficas (volumen y años).
_PATRON_RANGO_ANIOS = re.compile(r"(19|20)\d\d\s*[-–]\s*(19|20)\d\d")  # noqa: RUF001
# Solo formatos inequívocos: con paréntesis, con guiones o con código de país. Un número
# separado solo por espacios ("600 3200 6400") suele ser una fila de una tabla.
_PATRON_TELEFONO = re.compile(
    r"(?<![\d.,])("
    r"\+\d{1,3}[\s-]?\(?\d{2,3}\)?[\s-]?\d{3,4}[\s-]\d{4}"  # +52 81 1234 5678
    r"|\(\d{2,3}\)\s?\d{3,4}-\d{4}"  # (81) 1234-5678
    r"|\d{2,3}-\d{3,4}-\d{4}"  # 81-1234-5678
    r")(?![\d.,])"
)
_PATRON_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b")

# --- Unidades ---------------------------------------------------------------------------
_CANTIDAD = r"(\d(?:[\d.,\s-]*\d)?\s*\|?\s*)"  # "5", "0,5-1", "10-20|" (tablas)
# "ug" no es una unidad: es "µg" escrito sin el símbolo. Se corrige siempre.
_PATRON_UG = re.compile(_CANTIDAD + r"(ug)(?=(/[A-Za-z²]+))")
# "μg" (letra griega mu) y "µg" (símbolo micro) se ven igual; se unifica en "µ".
_PATRON_MU_GRIEGA = re.compile(_CANTIDAD + r"(μg)(?=(/[A-Za-z²]+))")
# "pg" y "1g" delante de "/kg" pueden ser "µg" mal leído por el OCR... o un "pg/kg" o
# "1 g/kg" reales. Solo se corrigen en documentos con OCR y en líneas de dosis. ("yg" no es
# una unidad real: se corrige siempre, con la tabla CONFUSIONES_OCR de unidades.py.)
_PATRON_MICRO_OCR = re.compile(_CANTIDAD + r"(pg|1g)(?=(/kg))")


class TipoCambio(StrEnum):
    """Categorías del reporte de limpieza."""

    LINEA_REPETIDA = "linea_repetida"
    NUMERO_PAGINA = "numero_pagina"
    DATO_PERSONAL = "dato_personal"
    UNIDAD_CORREGIDA = "unidad_corregida"
    UNIDAD_SOSPECHOSA = "unidad_sospechosa"  # solo se reporta, no se cambia


@dataclass(frozen=True, slots=True)
class Cambio:
    """Una fila del reporte de limpieza."""

    tipo: TipoCambio
    regla: str
    original: str
    reemplazo: str = ""
    pagina: int | None = None
    veces: int = 1


@dataclass(slots=True)
class Pagina:
    """Texto de una página; ``numero`` es ``None`` en documentos sin páginas (PowerPoint)."""

    numero: int | None
    texto: str


@dataclass(slots=True)
class DocumentoLimpio:
    """Resultado de limpiar un documento."""

    texto: str
    cambios: list[Cambio] = field(default_factory=list)


# --- Estructura del archivo ------------------------------------------------------------


def separar_cabecera(markdown: str) -> tuple[str, str]:
    """Separa la cabecera YAML (``---`` … ``---``) del cuerpo."""
    if markdown.startswith("---\n"):
        fin = markdown.index("\n---\n", 4) + len("\n---\n")
        return markdown[:fin], markdown[fin:]
    return "", markdown


def dividir_paginas(cuerpo: str) -> list[Pagina]:
    """Divide el cuerpo por las marcas ``<!-- pagina: N -->``."""
    partes = PATRON_MARCA_PAGINA.split(cuerpo)
    if len(partes) == 1:  # sin marcas: documento sin páginas
        return [Pagina(None, cuerpo)]
    # split con un grupo devuelve: [antes, número, texto, número, texto, ...]
    return [
        Pagina(int(numero), texto) for numero, texto in zip(partes[1::2], partes[2::2], strict=True)
    ]


def unir(paginas: Sequence[Pagina]) -> str:
    """Vuelve a unir las páginas, con sus marcas."""
    bloques = [
        (
            p.texto.strip()
            if p.numero is None
            else f"{MARCA_PAGINA.format(numero=p.numero)}\n{p.texto.strip()}"
        )
        for p in paginas
    ]
    return "\n\n".join(b.rstrip() for b in bloques) + "\n"


# --- 1. Líneas repetidas ---------------------------------------------------------------


def clave_linea(linea: str) -> str:
    """Forma de comparar líneas: sin espacios de más y con los números **de los extremos**
    como ``#``.

    Así ``… Página 12`` y ``… Página 13`` cuentan como la misma línea, pero dos líneas de
    contenido que solo cambian en un número interno (``La catalasa 3 …``) siguen siendo
    distintas.
    """
    texto = re.sub(r"\s+", " ", linea).strip()
    texto = re.sub(r"\d+(?=\W*$)", "#", texto)  # número al final
    return re.sub(r"^(\W*)\d+", r"\1#", texto)  # número al inicio


def _es_linea_protegida(linea: str) -> bool:
    """Líneas que nunca se consideran encabezados: tablas y líneas vacías."""
    texto = linea.strip()
    return not texto or texto.startswith("|")


def detectar_lineas_repetidas(paginas: Sequence[Pagina]) -> Counter[str]:
    """Claves de las líneas que aparecen en al menos la mitad de las páginas."""
    if len(paginas) < MIN_PAGINAS_PARA_REPETIDAS:
        return Counter()
    apariciones: Counter[str] = Counter()
    for pagina in paginas:
        claves = {
            clave_linea(linea)
            for linea in pagina.texto.splitlines()
            if not _es_linea_protegida(linea)
        }
        apariciones.update(claves)
    minimo = PROPORCION_MIN_REPETIDA * len(paginas)
    return Counter({clave: n for clave, n in apariciones.items() if n >= minimo})


def quitar_lineas_repetidas(paginas: Sequence[Pagina]) -> list[Cambio]:
    """Elimina de cada página las líneas repetidas (modifica ``paginas``)."""
    repetidas = detectar_lineas_repetidas(paginas)
    if not repetidas:
        return []
    ejemplos: dict[str, str] = {}
    for pagina in paginas:
        conservadas = []
        for linea in pagina.texto.splitlines():
            clave = clave_linea(linea)
            if not _es_linea_protegida(linea) and clave in repetidas:
                ejemplos.setdefault(clave, linea.strip())
            else:
                conservadas.append(linea)
        pagina.texto = "\n".join(conservadas)
    return [
        Cambio(TipoCambio.LINEA_REPETIDA, "en ≥50 % de las páginas", ejemplos[clave], veces=n)
        for clave, n in repetidas.items()
        if clave in ejemplos
    ]


# --- 2. Datos personales -----------------------------------------------------------------


def _sustituir(
    patron: re.Pattern[str],
    regla: str,
    linea: str,
    pagina: int | None,
    cambios: list[Cambio],
    excepto: re.Pattern[str] | None = None,
) -> str:
    """Reemplaza cada coincidencia de ``patron`` por la marca, salvo las que contengan
    ``excepto`` (p. ej. un rango de años que parece teléfono)."""

    def reemplazar(coincidencia: re.Match[str]) -> str:
        if excepto is not None and excepto.search(coincidencia.group(0)):
            return coincidencia.group(0)
        cambios.append(
            Cambio(
                TipoCambio.DATO_PERSONAL, regla, coincidencia.group(0), MARCA_DATO_PERSONAL, pagina
            )
        )
        return MARCA_DATO_PERSONAL

    return patron.sub(reemplazar, linea)


def quitar_datos_personales(texto: str, pagina: int | None = None) -> tuple[str, list[Cambio]]:
    """Elimina nombres junto a etiquetas, listas de equipo, matrículas, teléfonos y correos."""
    cambios: list[Cambio] = []
    resultado: list[str] = []
    en_lista_equipo = False
    for linea in texto.splitlines():
        # Lista de integrantes: "Equipo:" seguido de líneas que son solo nombres.
        if _PATRON_INICIO_EQUIPO.match(linea):
            en_lista_equipo = True
            resultado.append(linea)
            continue
        if en_lista_equipo:
            if not linea.strip():
                resultado.append(linea)
                continue
            if _PATRON_LINEA_NOMBRE.match(linea):
                cambios.append(
                    Cambio(
                        TipoCambio.DATO_PERSONAL,
                        "lista de equipo",
                        linea.strip(),
                        MARCA_DATO_PERSONAL,
                        pagina,
                    )
                )
                resultado.append(MARCA_DATO_PERSONAL)
                continue
            en_lista_equipo = False

        if _PATRON_NOMBRE_CON_MATRICULA.match(linea):
            cambios.append(
                Cambio(
                    TipoCambio.DATO_PERSONAL,
                    "nombre con matrícula",
                    linea.strip(),
                    MARCA_DATO_PERSONAL,
                    pagina,
                )
            )
            resultado.append(MARCA_DATO_PERSONAL)
            continue

        linea = _sustituir(_PATRON_ETIQUETA_PERSONAL, "etiqueta personal", linea, pagina, cambios)
        linea = _sustituir(_PATRON_CORREO, "correo", linea, pagina, cambios)
        linea = _sustituir(
            _PATRON_TELEFONO_ETIQUETA, "teléfono con etiqueta", linea, pagina, cambios
        )
        linea = _sustituir(
            _PATRON_TELEFONO, "teléfono", linea, pagina, cambios, excepto=_PATRON_RANGO_ANIOS
        )
        resultado.append(linea)
    return "\n".join(resultado), cambios


# --- 3. Unidades ----------------------------------------------------------------------------


def corregir_unidades(
    texto: str, pagina: int | None = None, con_ocr: bool = False
) -> tuple[str, list[Cambio]]:
    """Corrige ``µg`` mal escrito o mal leído y reporta unidades fuera del catálogo.

    - ``ug`` → ``µg``: siempre.
    - ``pg``, ``1g`` + ``/kg`` → ``µg/kg``: solo si el documento pasó por OCR **y**
      la línea tiene contexto de dosis (IV, IM, CRI, bolo…). En un documento digital el
      texto es exacto: si dice ``pg/kg``, es ``pg/kg``.
    - Confusiones típicas del OCR (``rng`` → ``mg``, ``Ul`` → ``UI``, ``llg`` → ``µg``): se
      corrigen con la tabla ``CONFUSIONES_OCR`` de ``unidades.py``.
    - Unidades que no están en el catálogo (``1a/kg``, ``ma/kg``): solo se reportan.
    """
    cambios: list[Cambio] = []

    def reemplazador(regla: str) -> Callable[[re.Match[str]], str]:
        def reemplazar(coincidencia: re.Match[str]) -> str:
            corregido = coincidencia.group(1) + "µg"
            denominador = coincidencia.group(3)  # "/kg", "/dl"… (no se consume, solo se lee)
            cambios.append(
                Cambio(TipoCambio.UNIDAD_CORREGIDA, regla, coincidencia.group(0) + denominador,
                       corregido + denominador, pagina)
            )  # fmt: skip
            return corregido

        return reemplazar

    lineas = []
    for linea in texto.splitlines():
        linea = _PATRON_UG.sub(reemplazador("ug → µg"), linea)
        linea = _PATRON_MU_GRIEGA.sub(reemplazador("μ griega → µ (mismo símbolo)"), linea)
        if con_ocr and tiene_contexto_de_dosis(linea):
            linea = _PATRON_MICRO_OCR.sub(reemplazador("µ mal leído por el OCR"), linea)
        lineas.append(linea)
    texto = "\n".join(lineas)

    texto, confusiones = corregir_confusiones_ocr(texto)
    cambios.extend(
        Cambio(TipoCambio.UNIDAD_CORREGIDA, regla, original, corregido, pagina)
        for original, corregido, regla in confusiones
    )
    cambios.extend(
        Cambio(TipoCambio.UNIDAD_SOSPECHOSA, "no está en el catálogo", contexto, pagina=pagina)
        for contexto in buscar_unidades_desconocidas(texto)
    )
    return texto, cambios


# --- 4. Números de página y espacios ----------------------------------------------------------


def quitar_numeros_pagina(texto: str, pagina: int | None = None) -> tuple[str, list[Cambio]]:
    """Quita las líneas que solo son un número de página (``12``, ``- 12 -``, ``Página 12``)."""
    cambios: list[Cambio] = []
    conservadas = []
    for linea in texto.splitlines():
        if linea.strip() and _PATRON_NUMERO_PAGINA.match(linea):
            cambios.append(
                Cambio(
                    TipoCambio.NUMERO_PAGINA,
                    "línea con solo un número",
                    linea.strip(),
                    pagina=pagina,
                )
            )
        else:
            conservadas.append(linea)
    return "\n".join(conservadas), cambios


def normalizar_espacios(texto: str) -> str:
    """Sin espacios al final de las líneas y con máximo una línea en blanco seguida."""
    lineas = [linea.rstrip() for linea in texto.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


# --- Documento completo -------------------------------------------------------------------------


def limpiar_markdown(markdown: str, con_ocr: bool = False) -> DocumentoLimpio:
    """Aplica las cuatro tareas de limpieza a un documento convertido.

    ``con_ocr`` indica si el documento pasó por OCR (solo así se corrigen ``pg``/``yg``/``1g``).
    """
    cabecera, cuerpo = separar_cabecera(markdown)
    paginas = dividir_paginas(cuerpo)
    cambios = quitar_lineas_repetidas(paginas)
    for pagina in paginas:
        texto = pagina.texto
        pasos = (
            quitar_datos_personales,
            partial(corregir_unidades, con_ocr=con_ocr),
            quitar_numeros_pagina,
        )
        for paso in pasos:
            texto, nuevos = paso(texto, pagina.numero)
            cambios.extend(nuevos)
        pagina.texto = normalizar_espacios(texto)
    return DocumentoLimpio(cabecera + unir(paginas), cambios)


@dataclass(frozen=True, slots=True)
class ResultadoLimpieza:
    """Una fila del manifiesto de limpieza."""

    ruta_relativa: Path
    ruta_limpia: Path | None
    cambios: Counter[TipoCambio]
    caracteres_antes: int = 0
    caracteres_despues: int = 0
    mensaje: str = ""


def ejecutar_limpieza(
    documentos: Sequence[DocumentoSeleccionado],
    ruta_markdown_crudo: Path,
    ruta_salida: Path,
    documentos_con_ocr: frozenset[str] = frozenset(),
) -> tuple[list[ResultadoLimpieza], list[tuple[Path, Cambio]]]:
    """Limpia cada documento convertido. Siempre se rehace: es rápido y así un ajuste en las
    reglas se aplica a todo."""
    resultados: list[ResultadoLimpieza] = []
    reporte: list[tuple[Path, Cambio]] = []
    for numero, documento in enumerate(documentos, start=1):
        origen = ruta_markdown(ruta_markdown_crudo, documento.ruta_relativa)
        if not origen.exists():
            mensaje = "No existe el Markdown: corre primero el paso 'convertir'"
            resultados.append(
                ResultadoLimpieza(documento.ruta_relativa, None, Counter(), mensaje=mensaje)
            )
            logger.error(
                "[%d/%d] %s: %s", numero, len(documentos), documento.ruta_relativa.name, mensaje
            )
            continue
        crudo = origen.read_text(encoding="utf-8")
        limpio = limpiar_markdown(crudo, con_ocr=str(documento.ruta_relativa) in documentos_con_ocr)
        destino = ruta_markdown(ruta_salida, documento.ruta_relativa)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(limpio.texto, encoding="utf-8")

        conteo = Counter(c.tipo for c in limpio.cambios)
        resultados.append(
            ResultadoLimpieza(
                documento.ruta_relativa, destino, conteo, len(crudo), len(limpio.texto)
            )
        )
        reporte.extend((documento.ruta_relativa, c) for c in limpio.cambios)
        logger.info(
            "[%d/%d] %s  %s",
            numero,
            len(documentos),
            ", ".join(f"{tipo}={n}" for tipo, n in sorted(conteo.items())) or "sin cambios",
            documento.ruta_relativa.name,
        )
    return resultados, reporte


def escribir_manifiesto(resultados: Sequence[ResultadoLimpieza], destino: Path) -> None:
    """Resumen por documento: la entrada del paso de chunking."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tipos = list(TipoCambio)
    with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            (
                "ruta_relativa",
                "ruta_limpia",
                "caracteres_antes",
                "caracteres_despues",
                *tipos,
                "mensaje",
            )
        )
        for r in resultados:
            escritor.writerow(
                (r.ruta_relativa, r.ruta_limpia or "", r.caracteres_antes, r.caracteres_despues,
                 *(r.cambios[t] for t in tipos), r.mensaje)
            )  # fmt: skip


def escribir_reporte(reporte: Sequence[tuple[Path, Cambio]], destino: Path) -> None:
    """Cada cambio realizado, para revisarlo a mano."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            ("ruta_relativa", "pagina", "tipo", "regla", "veces", "original", "reemplazo")
        )
        for ruta, c in reporte:
            escritor.writerow(
                (ruta, c.pagina or "", c.tipo, c.regla, c.veces, c.original, c.reemplazo)
            )
