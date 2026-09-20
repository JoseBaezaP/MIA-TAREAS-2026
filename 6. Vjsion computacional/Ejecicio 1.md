# Reporte — YOLOv8

**¿Qué detectó YOLO?**
En vez de usar las fotos de ejemplo de Ultralytics (zidane.jpg y bus.jpg), corrí el notebook con otras dos fotos de internet. En la celda del CLI, YOLO detectó un **perro**. En la celda con `model(...)`, detectó un **carro**.

**¿Faltó algo por etiquetar?**
Sí, en las dos fotos solo salió una etiqueta cuando había más cosas en la imagen. Puede pasar porque:

- ese objeto no es una de las 80 clases que YOLO conoce (COCO),
- está muy chiquito o cortado en la foto,
- o su confianza salió más baja que el umbral (0.25) y por eso no se muestra.

**¿El CLI y el `model(...)` dieron lo mismo?**
No se puede comparar porque usé fotos distintas en cada celda (el CLI con la del perro, y el `model(...)` con la del carro). Si se usara la misma foto en las dos, deberían dar el mismo resultado, porque por dentro usan el mismo modelo.

**Evidencia de GPU en Colab**

```
Ultralytics 8.4.150 CUDA:0 (Tesla T4, 14913MiB)
```

Esto confirma que corrí con GPU activada.
