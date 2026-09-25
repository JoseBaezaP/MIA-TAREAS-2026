# agente/ — F3: Agente RAG con LangGraph · ⏳ pendiente

Grafo de LangGraph que responde solo con base en la biblioteca y cita la fuente:

```
pregunta → reformular → buscar (pgvector) → ¿los fragmentos sirven?
                            ▲                   ├─ no → reformular y buscar otra vez
                            └───────────────────┘
                                                └─ sí → responder citando libro y página
```

| Archivo | Responsabilidad |
|---|---|
| `estado.py` | Estado compartido entre los nodos del grafo |
| `nodos.py` | Cada paso: reformular, buscar, evaluar, responder |
| `grafo.py` | Cómo se conectan los nodos y las condiciones |
| `prompts.py` | Instrucciones para el LLM |
