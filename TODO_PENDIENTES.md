# TODO Pendientes

## 1. sectores_json — inconsistencia de columnas entre `guardar_reportes` y `leer_registros`

`leer_registros()` devuelve la columna `sectores_json` (agregada en `_asegurar_columna_sectores_json` dentro de `crear_tablas()`), pero `preparar_dataframe()` no la incluye. Esto provoca que:

- `test_guardar_reportes_escribe_sqlite_temporal_correctamente` falle en `assert list(resultado_sqlite.columns) == list(esperado.columns)`
- `test_guardar_reportes_mantiene_columnas_esperadas` falle por la misma razón

**Decisión pendiente**: ¿`leer_registros()` debe filtrar `sectores_json` de los resultados? ¿O `preparar_dataframe()` debe incluirla? Depende de si `sectores_json` es un campo operacional que debe exportarse al Excel o solo un campo interno de la BD.

---

## 2. Formato de excepción en `ejecutar_guardado_reporte` incluye traceback completo

El handler de error en `report_service.ejecutar_guardado_reporte()` formatea el mensaje como `f"{exc!r}\n\nTraceback:\n{tb_str}"` (incluye traceback completo), pero `test_ejecutar_guardado_reporte_error_guardado_retorna_error` espera `str(exc)` limpio (solo el mensaje de la excepción).

**Decisión pendiente**: ¿El formato con traceback es intencional (útil para debugging en producción)? Si es así, actualizar el test para que verifique que el mensaje *contiene* el texto de la excepción en vez de igualdad exacta. Si fue un descuido, revertir el formato al `str(exc)` original.
