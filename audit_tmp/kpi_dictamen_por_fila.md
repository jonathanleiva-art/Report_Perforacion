# Dictamen KPI por fila

Base consultada: `reportes_perforacion.db`, tabla `registros_perforacion`.
Formula vigente: disponibilidad = (Horas turno - Averia - Mantencion Programada) / Horas turno * 100. Standby no descuenta disponibilidad.

Nota de contraste: en esta SQLite actual no se reproducen las 34 diferencias de disponibilidad descritas en la auditoria pegada; la disponibilidad guardada ya coincide para los 46 IDs revisados. Las diferencias residuales detectadas aqui son 3 casos de utilizacion frente a la formula vigente.

## Resumen

- total: 46
- coherente: 27
- revisar: 19
- dif_disp: 0
- dif_util: 3
- dif_rend: 0

## Detalle

| ID | Fecha | Turno | Equipo | Operador | Clase | Disp. guardada | Disp. recalc. | Dif. disp. | Util. dif. | Rend. dif. | Dictamen |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| 984 | 2026-05-14 | Noche | FlexiROC D65 9274 | Mauricio Mora | REVISAR | 95.83 | 95.83 | -0.00 | -2.45 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 985 | 2026-05-14 | Noche | SmartROC D65 9339 | Nicolas Torres | REVISAR | 50.00 | 50.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 986 | 2026-05-14 | Noche | FlexiROC D65 9272 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 987 | 2026-05-14 | Noche | FlexiROC D65 9259 | Matías Toro | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 988 | 2026-05-14 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | REVISAR | 100.00 | 100.00 | 0.00 | -0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria |
| 989 | 2026-05-14 | Noche | Sandvik D75KS 9277 | Carlos Rondon | REVISAR | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles |
| 990 | 2026-05-15 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 991 | 2026-05-15 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 993 | 2026-05-15 | Noche | SmartROC D65 9339 | Nicolas Torres | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 994 | 2026-05-15 | Noche | FlexiROC D65 9272 | Mauricio Mora | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 995 | 2026-05-15 | Noche | FlexiROC D65 9259 | Matías Toro | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 996 | 2026-05-16 | Noche | Sandvik D75KS 9277 | Carlos Rondon | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 997 | 2026-05-16 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 998 | 2026-05-16 | Noche | FlexiROC D65 9259 | Matías Toro | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 999 | 2026-05-16 | Noche | SmartROC D65 9339 | Nicolas Torres | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1000 | 2026-05-16 | Noche | FlexiROC D65 9272 | Mauricio Mora | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1001 | 2026-05-16 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1004 | 2026-05-17 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1005 | 2026-05-17 | Noche | FlexiROC D65 9272 | Mauricio Mora | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1007 | 2026-05-17 | Noche | SmartROC D65 9339 | Nicolas Torres | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1008 | 2026-05-18 | Noche | FlexiROC D65 9272 | Mauricio Mora | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1009 | 2026-05-18 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1012 | 2026-05-18 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1013 | 2026-05-18 | Noche | SmartROC D65 9339 | Nicolas Torres | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1014 | 2026-05-19 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en mantencion programada; disponibilidad queda en 0% |
| 1023 | 2026-05-20 | Día | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1026 | 2026-05-21 | Noche | SmartROC D65 9339 | Nicolas Torres | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1027 | 2026-05-21 | Noche | FlexiROC D65 9272 | Mauricio Mora | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1031 | 2026-05-21 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1034 | 2026-05-22 | Noche | FlexiROC D65 9259 | Matías Toro | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1036 | 2026-05-22 | Noche | FlexiROC D65 9272 | Mauricio Mora | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1039 | 2026-05-23 | Noche | FlexiROC D65 9272 | Mauricio Mora | REVISAR | 22.92 | 22.92 | 0.00 | -28.03 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1040 | 2026-05-23 | Noche | SmartROC D65 9339 | Nicolas Torres | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1042 | 2026-05-23 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | COHERENTE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en mantencion programada; disponibilidad queda en 0% |
| 1044 | 2026-05-24 | Noche | Sandvik D75KS 9245 | Valeria Millan | COHERENTE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en mantencion programada; disponibilidad queda en 0% |
| 1046 | 2026-05-24 | Noche | FlexiROC D65 9274 | Jhan Calderon | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1047 | 2026-05-24 | Noche | SmartROC D65 9339 | Nicolas Torres | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1050 | 2026-05-25 | Noche | Sandvik D75KS 9245 | Jonathan Leiva | COHERENTE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en mantencion programada; disponibilidad queda en 0% |
| 1053 | 2026-05-25 | Noche | SmartROC D65 9339 | Nicolas Torres | REVISAR | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1057 | 2026-05-26 | Noche | Sandvik D75KS 9277 | Carlos Rondon | REVISAR | 100.00 | 100.00 | 0.00 | -0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene standby/sin marcacion; la regla actual no lo resta de disponibilidad; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1060 | 2026-05-26 | Noche | FlexiROC D65 9272 | Mauricio Mora | COHERENTE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en mantencion programada; disponibilidad queda en 0% |
| 1063 | 2026-05-27 | Noche | Sandvik D75KS 9277 | Valeria Millan | COHERENTE | 100.00 | 100.00 | 0.00 | 0.00 | 0.00 | Patron valido: turno completo en standby; standby no descuenta disponibilidad en formula vigente |
| 1064 | 2026-05-27 | Noche | SmartROC D65 9339 | Nicolas Torres | REVISAR | 54.17 | 54.17 | 0.00 | -31.73 | -0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1065 | 2026-05-27 | Noche | FlexiROC D65 9272 | Mauricio Mora | REVISAR | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles; Contexto operacional indica equipo detenido/fuera de servicio/standby |
| 1066 | 2026-05-27 | Noche | FlexiROC D65 9274 | Jhan Calderon | REVISAR | 95.83 | 95.83 | -0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles |
| 1067 | 2026-05-27 | Noche | FlexiROC D65 9259 | Matías Toro | REVISAR | 45.83 | 45.83 | -0.00 | 0.00 | 0.00 | Disponibilidad coincide con formula vigente; revisar por contexto operacional marcado en auditoria; Contiene averia; la regla actual resta averia de horas disponibles |
