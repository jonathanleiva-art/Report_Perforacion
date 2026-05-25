Modulo ML - Report_Perforacion

Objetivo:
Entregar una primera capa de analisis predictivo de apoyo operacional, sin reemplazar el criterio del operador, supervisor ni mantenedor.

Fuente de datos:
- SQLite principal: reportes_perforacion.db
- Tabla: registros_perforacion
- El modulo no modifica registros historicos.

Variables consideradas:
- equipo
- operador
- turno
- tipo de perforacion
- condicion de terreno
- horas efectivas
- horas no efectivas
- horas de averia
- metros perforados
- disponibilidad
- utilizacion
- rendimiento

Modo actual:
Con menos de 100 registros, el sistema usa reglas heuristicas:
- Utilizacion < 40% implica riesgo alto de baja utilizacion.
- Rendimiento en cero o bajo respecto al cuartil inferior implica riesgo medio/alto.
- Disponibilidad < 70% u horas de averia implican riesgo de mantenimiento.
- Turnos sin metros y sin horas efectivas implican alta probabilidad de turno improductivo.

ML real:
Cuando existan al menos 100 registros y scikit-learn este instalado, model_training.py permite entrenar un RandomForestClassifier inicial para riesgo de baja utilizacion.

Advertencia:
Modelo de apoyo, no reemplaza criterio operacional. Las recomendaciones se basan solo en datos registrados y deben interpretarse junto con el contexto del turno.
