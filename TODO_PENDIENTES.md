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

---

## 3. [PRIORIDAD BAJA] test_import_excel_page.py — página renombrada/eliminada

4 tests fallan porque buscan `pages/12_Importar_Excel.py` que ya no existe:

- `test_nombre_archivo_seguro_limpia_ruta_y_caracteres`
- `test_guardar_upload_temporal_usa_timestamp_y_no_sobrescribe`
- `test_fuente_confirmable_bloquea_desconocido_error_o_faltantes`
- `test_construir_observacion_diagnostico_incluye_resumen`

**Acción pendiente**: Eliminar estos tests o actualizarlos para apuntar al archivo de página correcto (si la funcionalidad sigue existiendo bajo otro nombre).

---

## 4. [PRIORIDAD BAJA] Dependencias faltantes — xlrd y PyMuPDF

7 tests fallan por paquetes no instalados en el entorno:

**xlrd** (5 tests en `test_ciclos_service.py`):
- `test_leer_excel_ciclos_detecta_columnas_y_filas`
- `test_importar_excel_ciclos_crea_tabla_separada_y_evita_duplicados`
- `test_importar_excel_ciclos_registra_fuentes_y_filtra_por_id_fuente`
- `test_ciclos_operacional_muestra_nombre_o_codigo_segun_tabla_operadores`
- `test_actualizar_operador_recalcula_ciclos_sin_reimportar`

**PyMuPDF** (2 tests en `test_malla_pdf_preview_real_service.py`):
- `test_generar_preview_pdf_real_crea_png_desde_primer_pagina`
- `test_obtener_preview_plano_malla_usa_rasterizacion_real`

**Acción pendiente**: `pip install xlrd pymupdf` en el entorno de desarrollo, o marcar estos tests con `pytest.importorskip` para que se salten automáticamente si el paquete no está disponible.
