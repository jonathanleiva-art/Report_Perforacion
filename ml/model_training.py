from dataclasses import dataclass
import importlib.util

from ml.features import agregar_targets_operacionales, preparar_features
from ml.predictor import MIN_REGISTROS_ML


@dataclass
class TrainingResult:
    trained: bool
    status: str
    records: int
    model_type: str = ""
    metrics: dict | None = None


def sklearn_disponible():
    return importlib.util.find_spec("sklearn") is not None


def entrenar_modelos(df):
    features = preparar_features(df)
    total = len(features)
    if total < MIN_REGISTROS_ML:
        return TrainingResult(
            trained=False,
            status=f"No se entrena ML real: se requieren {MIN_REGISTROS_ML} registros y hay {total}.",
            records=total,
        )

    if not sklearn_disponible():
        return TrainingResult(
            trained=False,
            status="No se entrena ML real: scikit-learn no está instalado.",
            records=total,
        )

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import OneHotEncoder
        from sklearn.compose import ColumnTransformer
        from sklearn.pipeline import Pipeline
        from sklearn.metrics import accuracy_score

        data = agregar_targets_operacionales(features)
        target = "target_baja_utilizacion"
        x = data.drop(columns=[
            "target_baja_utilizacion",
            "target_bajo_rendimiento",
            "target_turno_improductivo",
        ])
        y = data[target]
        if y.nunique() < 2:
            return TrainingResult(
                trained=False,
                status="No se entrena ML real: el target no tiene suficientes clases distintas.",
                records=total,
            )

        categoricas = [col for col in x.columns if x[col].dtype == "object"]
        numericas = [col for col in x.columns if col not in categoricas]
        preprocessor = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), categoricas),
            ("num", "passthrough", numericas),
        ])
        model = Pipeline([
            ("features", preprocessor),
            ("model", RandomForestClassifier(n_estimators=100, random_state=42)),
        ])
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=42, stratify=y)
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        return TrainingResult(
            trained=True,
            status="Modelo RandomForestClassifier entrenado para riesgo de baja utilización.",
            records=total,
            model_type="RandomForestClassifier",
            metrics={"accuracy": round(float(accuracy_score(y_test, pred)), 4)},
        )
    except Exception as exc:
        return TrainingResult(
            trained=False,
            status=f"No se pudo entrenar ML real; se mantiene modo heurístico. Detalle: {exc}",
            records=total,
        )
