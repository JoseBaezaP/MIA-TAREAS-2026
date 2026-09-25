# ingesta/ — F2: De PDF a vectores · ⏳ pendiente

Convierte los documentos aprobados en la F1 en vectores guardados en pgvector:

```
PDF ─► ocr.py ─► conversion.py ─► limpieza.py ─► chunking.py ─► vectorizacion.py ─► pgvector
       (ocrmypdf) (anydoc → Markdown) (ruido)    (~800 tokens)   (Voyage voyage-4)
```

Cada paso escribe su salida en `data/0X_*/`, así que el proceso se puede retomar desde
cualquier paso sin repetir los anteriores.
