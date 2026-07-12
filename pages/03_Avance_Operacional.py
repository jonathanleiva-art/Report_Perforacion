from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from ui.formatting import dataframe_visible, texto_visible
import db
import math
import pandas as pd
import plotly.graph_objects as go
import re
import io


def normalizar_mallas(texto_malla):
    """
    Convierte '108, 109, 114' en ['108', '109', '114']
    Convierte '114' en ['114']
    """
    if not texto_malla:
        return []
    partes = re.split(r'[,;\s]+', str(texto_malla).strip())
    return [p.strip() for p in partes if p.strip().isdigit()]


def obtener_mallas_disponibles():
    with db.conectar_db() as conn:
        rows = conn.execute("""
            SELECT banco, fase, numero_malla,
                pozos_perforados, metros_perforados,
                operador, turno, fecha_turno,
                equipo, numero_equipo
            FROM avance_malla
            WHERE banco != '' AND numero_malla != ''
        """).fetchall()

    # Expandir registros con múltiples mallas
    expandido = []
    for r in rows:
        banco, fase, mallas_txt = r[0], r[1], r[2]
        pozos = r[3] or 0
        metros = r[4] or 0
        operador = r[5]
        turno = r[6]
        fecha = r[7]
        equipo = str(r[8] or "").strip()
        numero_equipo = str(r[9] or "").strip()
        equipo_completo = f"{equipo} {numero_equipo}".strip() if (equipo or numero_equipo) else ""
        mallas_lista = normalizar_mallas(mallas_txt)
        if not mallas_lista:
            continue
        # Distribuir pozos y metros entre mallas del registro
        n = len(mallas_lista)
        for malla in mallas_lista:
            expandido.append({
                "banco": banco,
                "fase": fase,
                "malla": malla,
                "pozos": pozos / n,
                "metros": metros / n,
                "operador": operador,
                "turno": turno,
                "fecha": fecha,
                "equipo_completo": equipo_completo,
            })

    if not expandido:
        return []

    df = pd.DataFrame(expandido)
    resumen = (
        df.groupby(["banco", "fase", "malla"])
        .agg(
            total_pozos=("pozos", "sum"),
            total_metros=("metros", "sum"),
            operadores=("operador", "nunique"),
            turnos=("fecha", "nunique"),
            equipos=("equipo_completo", lambda x: ", ".join(sorted(set(v for v in x if v)))),
        )
        .reset_index()
        .sort_values(["banco", "fase", "malla"])
    )
    resumen["total_pozos"] = resumen["total_pozos"].round(0).astype(int)
    resumen["total_metros"] = resumen["total_metros"].round(1)
    return resumen.values.tolist()


def obtener_detalle_malla(banco, fase, malla):
    with db.conectar_db() as conn:
        rows = conn.execute("""
            SELECT turno, operador, equipo, numero_equipo,
                   tipo_perforacion, fecha_turno,
                   pozos_perforados, metros_perforados,
                   numero_malla
            FROM avance_malla
            WHERE banco=? AND fase=?
            AND (
                numero_malla = ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
            )
            ORDER BY fecha_turno DESC, turno, operador
        """, (
            banco, fase, malla,
            f"{malla},%",
            f"%, {malla},%",
            f"%, {malla}",
        )).fetchall()

    resultado = []
    for r in rows:
        mallas_lista = normalizar_mallas(r[8])
        n = len(mallas_lista) if mallas_lista else 1
        if malla in mallas_lista or not mallas_lista:
            pozos_part = round((r[6] or 0) / n, 1)
            metros_part = round((r[7] or 0) / n, 1)
            resultado.append((
                r[0], r[1], r[2], r[3], r[4],
                r[5], pozos_part, metros_part, 1
            ))
    return resultado


def obtener_planificado(banco, fase, malla):
    with db.conectar_db() as conn:
        row = conn.execute("""
            SELECT total_pozos, total_pozos_produccion,
                   total_pozos_buffer1, total_pozos_buffer2,
                   total_pozos_precorte, metros_planificados
            FROM mallas_plano
            WHERE banco=? AND fase=? AND numero_malla=?
            AND estado='activa'
            ORDER BY id DESC LIMIT 1
        """, (banco, fase, malla)).fetchone()
    return row


def guardar_planificado(banco, fase, malla, total, prod, buf1, buf2, pre, metros):
    with db.conectar_db() as conn:
        conn.execute("""
            INSERT INTO mallas_plano
            (banco, fase, numero_malla, total_pozos,
             total_pozos_produccion, total_pozos_buffer1,
             total_pozos_buffer2, total_pozos_precorte,
             metros_planificados, fecha_carga, estado)
            VALUES (?,?,?,?,?,?,?,?,?,date('now'),'activa')
        """, (banco, fase, malla, total, prod, buf1, buf2, pre, metros))
        conn.commit()


def extraer_datos_plano_pdf(pdf_bytes):
    """
    Extrae pozos planificados desde PDF de plano Enaex.
    Busca patrones como:
    B1: 6.0x7.0 /6 1/2" /19 Pozos /...
    B2: 6.0x7.0 / 6 1/2"/19 Pozos /...
    Prod: 11 x 12.7 / 10 5/8" /63 Pozos/...
    Bord: 9.5x11 / 10 5/8" / 13 Pozos /...
    """
    try:
        import pdfplumber
        resultado = {
            "buffer1": 0, "buffer2": 0,
            "produccion": 0, "precorte": 0,
            "metros": 0.0, "malla": "",
            "banco": "", "raw_text": ""
        }
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            texto = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
        resultado["raw_text"] = texto

        # Buffer 1
        m = re.search(
            r'B1\s*:\s*[\d.x\s]+/\s*[\d\s/\"]+/\s*(\d+)\s*[Pp]ozos',
            texto)
        if m:
            resultado["buffer1"] = int(m.group(1))

        # Buffer 2
        m = re.search(
            r'B2\s*:\s*[\d.x\s]+/\s*[\d\s/\"]+/\s*(\d+)\s*[Pp]ozos',
            texto)
        if m:
            resultado["buffer2"] = int(m.group(1))

        # Producción
        for pat in [
            r'Prod\s*:\s*[\d.x\s]+/\s*[\d\s/\"]+/\s*(\d+)\s*[Pp]ozos',
            r'Prod\w*\s*:\s*[\d.x\s]+.*?/\s*(\d+)\s*[Pp]ozos',
        ]:
            m = re.search(pat, texto)
            if m:
                resultado["produccion"] = int(m.group(1))
                break

        # Precorte / Borde
        for pat in [
            r'Bord\w*\s*:\s*[\d.x\s]+/\s*[\d\s/\"]+/\s*(\d+)\s*[Pp]ozos',
            r'[Pp]recorte.*?/\s*(\d+)\s*[Pp]ozos',
        ]:
            m = re.search(pat, texto)
            if m:
                resultado["precorte"] = int(m.group(1))
                break

        # Metros (suma de todos los /NNN m/ encontrados)
        metros_vals = re.findall(r'/\s*(\d+(?:\.\d+)?)\s*m', texto)
        if metros_vals:
            resultado["metros"] = sum(float(v) for v in metros_vals)

        # Malla y banco desde línea "N° DE MALLA ... FECHA"
        m = re.search(r'N[°º]\s*DE\s*MALLA\s+([\d\s]+)', texto)
        if m:
            resultado["malla"] = m.group(1).strip()
        m = re.search(r'B(\d{4})', texto)
        if m:
            resultado["banco"] = m.group(1)

        return resultado
    except ImportError:
        return {"error": "pdfplumber no instalado"}
    except Exception as e:
        return {"error": str(e)}


def clasificar_tipo(tipo_texto):
    t = str(tipo_texto).lower()
    if 'precorte' in t or 'pre corte' in t:
        return 'Precorte'
    if 'buffer 2' in t or 'b2' in t:
        return 'Buffer 2'
    if 'buffer 1' in t or 'b1' in t or 'buffer' in t:
        return 'Buffer 1'
    return 'Producción'


def _render_mapa_pozos(pozos_perforados, total_pozos, total_metros=0.0, n_operadores=0, n_turnos=0):
    if total_pozos <= 0:
        return
    pozos_perforados = min(int(pozos_perforados), int(total_pozos))
    cols_grilla = math.ceil(math.sqrt(total_pozos))
    rows_grilla = math.ceil(total_pozos / cols_grilla)

    x_coords, y_coords, colores, textos = [], [], [], []
    for i in range(int(total_pozos)):
        x = i % cols_grilla
        y = i // cols_grilla
        x_coords.append(x)
        y_coords.append(y)
        if i < pozos_perforados:
            colores.append("#22c55e")
            textos.append(f"Pozo {i + 1}: Perforado")
        else:
            colores.append("#6b7280")
            textos.append(f"Pozo {i + 1}: Pendiente")

    fig = go.Figure(go.Scatter(
        x=x_coords, y=y_coords,
        mode="markers",
        marker=dict(
            size=14,
            color=colores,
            symbol="circle",
            line=dict(width=1, color="rgba(0,0,0,0.15)"),
        ),
        text=textos,
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        height=max(200, rows_grilla * 28),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, autorange="reversed"),
    )

    lc1, lc2, lc3 = app.st.columns(3)
    lc1.markdown("🟢 **Perforado**")
    lc2.markdown("⚫ **Pendiente**")
    lc3.markdown(f"**{pozos_perforados}/{total_pozos} pozos**")
    app.st.plotly_chart(fig, width="stretch")

    rc1, rc2, rc3, rc4 = app.st.columns(4)
    rc1.metric("Metros totales malla", f"{total_metros:,.1f} m")
    m_por_pozo = total_metros / pozos_perforados if pozos_perforados > 0 else 0.0
    rc2.metric("Metros / pozo", f"{m_por_pozo:.1f} m")
    rc3.metric("Operadores en malla", n_operadores)
    rc4.metric("Turnos trabajados", n_turnos)


def obtener_tendencia_malla(banco, fase, malla):
    with db.conectar_db() as conn:
        rows = conn.execute("""
            SELECT fecha_turno,
                   turno,
                   SUM(pozos_perforados) as pozos,
                   ROUND(SUM(metros_perforados),1) as metros,
                   COUNT(DISTINCT operador) as operadores
            FROM avance_malla
            WHERE banco=? AND fase=?
            AND (
                numero_malla = ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
            )
            AND fecha_turno IS NOT NULL
            AND fecha_turno != ''
            GROUP BY fecha_turno, turno
            ORDER BY fecha_turno ASC
        """, (
            banco, fase, malla,
            f"{malla},%", f"%, {malla},%", f"%, {malla}",
        )).fetchall()
    return rows


def obtener_ranking_operadores_malla(banco, fase, malla):
    with db.conectar_db() as conn:
        rows = conn.execute("""
            SELECT operador, turno, equipo,
                   SUM(pozos_perforados) as pozos,
                   ROUND(SUM(metros_perforados),1) as metros,
                   COUNT(DISTINCT fecha_turno) as dias_trabajados,
                   COUNT(*) as registros
            FROM avance_malla
            WHERE banco=? AND fase=?
            AND (
                numero_malla = ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
            )
            AND operador IS NOT NULL AND operador != ''
            GROUP BY operador, turno, equipo
            ORDER BY pozos DESC
        """, (
            banco, fase, malla,
            f"{malla},%", f"%, {malla},%", f"%, {malla}",
        )).fetchall()
    return rows


def obtener_resumen_equipos_malla(banco, fase, malla):
    with db.conectar_db() as conn:
        rows = conn.execute("""
            SELECT equipo, numero_equipo, operador, turno,
                   SUM(pozos_perforados) as pozos,
                   ROUND(SUM(metros_perforados),1) as metros,
                   COUNT(DISTINCT fecha_turno) as dias,
                   GROUP_CONCAT(DISTINCT tipo_perforacion) as tipos
            FROM avance_malla
            WHERE banco=? AND fase=?
            AND (
                numero_malla = ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
                OR numero_malla LIKE ?
            )
            AND equipo IS NOT NULL AND equipo != ''
            GROUP BY equipo, numero_equipo, operador, turno
            ORDER BY pozos DESC
        """, (
            banco, fase, malla,
            f"{malla},%", f"%, {malla},%", f"%, {malla}",
        )).fetchall()
    return rows


def normalizar_tipos_perforacion(texto):
    if not texto:
        return []
    tipos_raw = re.split(r"[,]+", str(texto))
    tipos = []
    vistos = set()
    for t in tipos_raw:
        t = t.strip()
        if not t or t in vistos:
            continue
        vistos.add(t)
        t_low = t.lower()
        if "precorte" in t_low or "pre corte" in t_low:
            tipos.append(("Precorte", "#639922", "#EAF3DE"))
        elif "buffer 2" in t_low or "b2" in t_low:
            tipos.append(("Buffer 2", "#185FA5", "#E6F1FB"))
        elif "buffer 1" in t_low or "buffer" in t_low:
            tipos.append(("Buffer 1", "#D97706", "#FAEEDA"))
        elif "producción" in t_low or "produccion" in t_low:
            tipos.append(("Producción", "#854F0B", "#FAEEDA"))
        elif "borde" in t_low or "border" in t_low:
            tipos.append(("Borde", "#533AB7", "#EEEDFE"))
        elif "repaso" in t_low:
            tipos.append(("Repaso", "#5F5E5A", "#F1EFE8"))
        elif "auxiliar" in t_low:
            tipos.append(("Auxiliar", "#0F6E56", "#E1F5EE"))
        else:
            tipos.append((t, "#5F5E5A", "#F1EFE8"))
    return tipos


def main():
    if not app.requerir_acceso():
        return

    render_page_header(
        app.st,
        "Avance de Malla",
        "Seguimiento de avance por banco, fase y malla · conectado a reportes operacionales"
    )

    mallas = obtener_mallas_disponibles()

    if not mallas:
        app.st.warning(
            "No hay datos de avance registrados aún. "
            "Ingresa reportes con banco, fase y malla para ver el avance."
        )
        return

    # ── Selector de malla ──────────────────────────────
    app.st.subheader("Seleccionar malla")
    c1, c2, c3 = app.st.columns(3)
    with c1:
        bancos = list(dict.fromkeys(r[0] for r in mallas))
        banco_sel = app.st.selectbox("Banco", bancos, key="av_banco")
    with c2:
        fases = list(dict.fromkeys(
            r[1] for r in mallas if r[0] == banco_sel))
        fase_sel = app.st.selectbox("Fase", fases, key="av_fase")
    with c3:
        mallas_fil = list(dict.fromkeys(
            r[2] for r in mallas
            if r[0] == banco_sel and r[1] == fase_sel))
        malla_sel = app.st.selectbox("Malla", mallas_fil, key="av_malla")

    fila = next(
        (r for r in mallas
         if r[0] == banco_sel and r[1] == fase_sel and r[2] == malla_sel),
        None)
    if not fila:
        return

    total_perf   = int(fila[3] or 0)
    total_metros = float(fila[4] or 0)
    n_operadores = int(fila[5] or 0)
    n_turnos     = int(fila[6] or 0)

    # ── Planificado ────────────────────────────────────
    plan = obtener_planificado(banco_sel, fase_sel, malla_sel)
    total_plan = int(plan[0]) if plan else 0

    # ── KPIs ──────────────────────────────────────────
    app.st.markdown("---")
    c1, c2, c3, c4, c5 = app.st.columns(5)
    c1.metric("Pozos perforados", f"{total_perf:,}")
    c2.metric("Metros perforados", f"{total_metros:,.1f} m")
    c3.metric("Operadores", n_operadores)
    c4.metric("Turnos registrados", n_turnos)
    if total_plan > 0:
        pct = min(round(total_perf / total_plan * 100, 1), 100)
        c5.metric("Avance", f"{pct}%",
                  delta=f"{total_perf}/{total_plan} pozos")
    else:
        c5.metric("Avance", "Sin plan",
                  delta="Ingresa total planificado abajo")

    # ── Barra de progreso ─────────────────────────────
    if total_plan > 0:
        pct_val = min(total_perf / total_plan, 1.0)
        app.st.progress(pct_val,
            text=f"Avance {pct}% — {total_perf} de {total_plan} pozos perforados")

    # ── Mapa visual de pozos ───────────────────────────
    if total_plan > 0:
        _render_mapa_pozos(
            pozos_perforados=total_perf,
            total_pozos=total_plan,
            total_metros=total_metros,
            n_operadores=n_operadores,
            n_turnos=n_turnos,
        )

    # ── Ingresar planificado ──────────────────────────
    with app.st.expander(
        "Ingresar total de pozos planificados para esta malla",
        expanded=(total_plan == 0)
    ):
        app.st.caption(
            "Ingresa los datos del plano PDF de Enaex. "
            "Solo se necesita hacer una vez por malla."
        )
        app.st.markdown("**Opción 1 — Leer desde PDF del plano Enaex**")
        pdf_file = app.st.file_uploader(
            "Sube el PDF del plano de perforación",
            type=["pdf"],
            key="plano_pdf_upload"
        )
        if pdf_file is not None:
            with app.st.spinner("Leyendo plano PDF..."):
                datos_pdf = extraer_datos_plano_pdf(
                    pdf_file.getvalue())
            if "error" in datos_pdf:
                if "pdfplumber" in datos_pdf["error"]:
                    app.st.warning(
                        "Instala pdfplumber: "
                        "pip install pdfplumber --break-system-packages"
                    )
                else:
                    app.st.error(
                        f"Error al leer PDF: {datos_pdf['error']}")
            else:
                app.st.success("PDF leído correctamente.")
                col_r1, col_r2 = app.st.columns(2)
                col_r1.metric(
                    "Producción detectada",
                    datos_pdf["produccion"])
                col_r1.metric(
                    "Buffer 1 detectado",
                    datos_pdf["buffer1"])
                col_r2.metric(
                    "Buffer 2 detectado",
                    datos_pdf["buffer2"])
                col_r2.metric(
                    "Precorte detectado",
                    datos_pdf["precorte"])
                total_det = (datos_pdf["produccion"] +
                             datos_pdf["buffer1"] +
                             datos_pdf["buffer2"] +
                             datos_pdf["precorte"])
                app.st.info(
                    f"Total detectado: {total_det} pozos")
                if datos_pdf.get("malla"):
                    app.st.caption(
                        f"Malla detectada en PDF: "
                        f"{datos_pdf['malla']}")
                if app.st.button(
                    "Usar estos datos del PDF",
                    type="primary",
                    key="btn_usar_pdf"
                ):
                    guardar_planificado(
                        banco_sel, fase_sel, malla_sel,
                        total_det,
                        datos_pdf["produccion"],
                        datos_pdf["buffer1"],
                        datos_pdf["buffer2"],
                        datos_pdf["precorte"],
                        datos_pdf["metros"]
                    )
                    app.st.success(
                        f"Planificado guardado desde PDF: "
                        f"{total_det} pozos.")
                    app.st.rerun()

        app.st.markdown("**Opción 2 — Ingresar manualmente**")
        col1, col2 = app.st.columns(2)
        with col1:
            inp_prod = app.st.number_input(
                "Pozos producción", min_value=0, value=0,
                step=1, key="plan_prod")
            inp_buf1 = app.st.number_input(
                "Pozos buffer 1", min_value=0, value=0,
                step=1, key="plan_buf1")
        with col2:
            inp_buf2 = app.st.number_input(
                "Pozos buffer 2", min_value=0, value=0,
                step=1, key="plan_buf2")
            inp_pre = app.st.number_input(
                "Pozos precorte", min_value=0, value=0,
                step=1, key="plan_pre")
        inp_metros = app.st.number_input(
            "Metros planificados totales", min_value=0.0,
            value=0.0, step=10.0, key="plan_metros")
        inp_total = inp_prod + inp_buf1 + inp_buf2 + inp_pre
        if inp_total > 0:
            app.st.info(
                f"Total calculado: {inp_total} pozos "
                f"(Prod:{inp_prod} B1:{inp_buf1} "
                f"B2:{inp_buf2} Pre:{inp_pre})")
        if app.st.button("Guardar planificado", type="primary",
                         key="btn_guardar_plan"):
            if inp_total == 0:
                app.st.error("Ingresa al menos un tipo de pozo.")
            else:
                guardar_planificado(
                    banco_sel, fase_sel, malla_sel,
                    inp_total, inp_prod, inp_buf1,
                    inp_buf2, inp_pre, inp_metros)
                app.st.success(
                    f"Planificado guardado: {inp_total} pozos totales.")
                app.st.rerun()

    # ── Detalle por turno ─────────────────────────────
    detalle = obtener_detalle_malla(banco_sel, fase_sel, malla_sel)
    if not detalle:
        return

    df = pd.DataFrame(detalle, columns=[
        "Turno", "Operador", "Equipo", "N°Equipo",
        "Tipo", "Fecha", "Pozos", "Metros", "Registros"
    ])
    df["Tipo_norm"] = df["Tipo"].apply(clasificar_tipo)

    app.st.markdown("---")
    app.st.subheader("Detalle por turno y operador")

    dia   = df[df["Turno"].str.lower().str.contains(
        "dia|día", na=False)]
    noche = df[df["Turno"].str.lower().str.contains(
        "noche", na=False)]

    col_d, col_n = app.st.columns(2)
    cols_vis = ["Fecha", "Operador", "Equipo",
                "Tipo_norm", "Pozos", "Metros"]

    with col_d:
        app.st.markdown(
            "<span style='color:#D97706;font-weight:500'>"
            "Turno día</span>", unsafe_allow_html=True)
        if dia.empty:
            app.st.info("Sin registros turno día.")
        else:
            app.st.dataframe(
                dataframe_visible(dia[cols_vis].rename(
                    columns={"Tipo_norm": "Tipo"})),
                hide_index=True, width="stretch")
            total_d = int(dia["Pozos"].sum())
            metros_d = round(float(dia["Metros"].sum()), 1)
            app.st.caption(
                f"Total día: {total_d} pozos · {metros_d} m")

    with col_n:
        app.st.markdown(
            "<span style='color:#3949AB;font-weight:500'>"
            "Turno noche</span>", unsafe_allow_html=True)
        if noche.empty:
            app.st.info("Sin registros turno noche.")
        else:
            app.st.dataframe(
                dataframe_visible(noche[cols_vis].rename(
                    columns={"Tipo_norm": "Tipo"})),
                hide_index=True, width="stretch")
            total_n = int(noche["Pozos"].sum())
            metros_n = round(float(noche["Metros"].sum()), 1)
            app.st.caption(
                f"Total noche: {total_n} pozos · {metros_n} m")

    # ── Desglose por tipo ─────────────────────────────
    app.st.markdown("---")
    app.st.subheader("Desglose por tipo de perforación")
    por_tipo = (
        df.groupby("Tipo_norm")
        .agg(Pozos=("Pozos", "sum"),
             Metros=("Metros", "sum"),
             Operadores=("Operador", "nunique"))
        .reset_index()
        .rename(columns={"Tipo_norm": "Tipo"})
    )
    por_tipo["Metros"] = por_tipo["Metros"].round(1)
    if total_plan > 0 and plan:
        plan_por_tipo = {
            "Producción": int(plan[1] or 0),
            "Buffer 1":   int(plan[2] or 0),
            "Buffer 2":   int(plan[3] or 0),
            "Precorte":   int(plan[4] or 0),
        }
        por_tipo["Planificado"] = por_tipo["Tipo"].map(
            lambda t: plan_por_tipo.get(t, 0))
        por_tipo["Avance %"] = por_tipo.apply(
            lambda r: round(r["Pozos"] / r["Planificado"] * 100, 1)
            if r["Planificado"] > 0 else "Sin plan", axis=1)
    app.st.dataframe(
        dataframe_visible(por_tipo),
        hide_index=True, width="stretch")

    # ── Tarjetas de equipos ───────────────────────
    equipos = obtener_resumen_equipos_malla(
        banco_sel, fase_sel, malla_sel)

    if equipos:
        app.st.markdown("---")
        app.st.markdown(
            "<div style='font-size:11px;font-weight:500;"
            "color:var(--color-text-secondary);"
            "text-transform:uppercase;letter-spacing:.08em;"
            f"margin-bottom:12px'>Equipos activos en malla "
            f"{malla_sel} · B{banco_sel} · F{fase_sel}</div>",
            unsafe_allow_html=True,
        )

        from utils import ruta_imagen_equipo
        import base64

        COLORES_EQUIPO = [
            "#D97706", "#185FA5", "#639922",
            "#854F0B", "#3949AB", "#0F6E56",
        ]

        def img_base64(modelo, numero):
            ruta = ruta_imagen_equipo(modelo, str(numero))
            if ruta and Path(ruta).exists():
                with open(ruta, "rb") as f:
                    ext = Path(ruta).suffix.lower()
                    mime = "jpeg" if ext in (".jpg", ".jpeg") else ext.replace(".", "")
                    return (
                        f"data:image/{mime};base64,"
                        f"{base64.b64encode(f.read()).decode()}"
                    )
            return None

        n_cols = min(len(equipos), 3)
        cols = app.st.columns(n_cols)

        for idx, eq in enumerate(equipos):
            modelo    = str(eq[0] or "")
            numero    = str(eq[1] or "")
            operador  = str(eq[2] or "")
            turno     = str(eq[3] or "")
            pozos     = int(eq[4] or 0)
            metros    = float(eq[5] or 0)
            dias      = int(eq[6] or 0)
            tipos_txt = str(eq[7] or "")

            tipos  = normalizar_tipos_perforacion(tipos_txt)
            aporte = round(pozos / max(total_perf, 1) * 100, 1)
            rend   = round(metros / pozos, 1) if pozos > 0 else 0
            color  = COLORES_EQUIPO[idx % len(COLORES_EQUIPO)]

            es_dia = "dia" in turno.lower() or "día" in turno.lower()
            turno_color = "#D97706" if es_dia else "#3949AB"
            turno_label = "☀ Día" if es_dia else "☾ Noche"

            tipos_html = "".join(
                f'<span style="font-size:10px;padding:2px 7px;'
                f'border-radius:4px;font-weight:500;'
                f'background:{bg};color:{c};margin:2px 2px 0 0;'
                f'display:inline-block">{n}</span>'
                for n, c, bg in tipos
            )

            img_src = img_base64(modelo, numero)
            if img_src:
                img_block = (
                    f'<img src="{img_src}" style="width:100%;'
                    f'height:160px;object-fit:cover;'
                    f'object-position:center center;display:block">'
                )
            else:
                img_block = (
                    '<div style="width:100%;height:160px;'
                    'background:var(--color-background-secondary);'
                    'display:flex;align-items:center;'
                    'justify-content:center;'
                    'font-size:11px;color:var(--color-text-secondary)">'
                    'Sin imagen</div>'
                )

            html = (
                f'<div style="background:var(--color-background-primary);'
                f'border:0.5px solid var(--color-border-tertiary);'
                f'border-radius:10px;overflow:hidden;position:relative">'
                f'<div style="height:3px;background:{color}"></div>'
                f'{img_block}'
                f'<div style="padding:10px 12px 0">'
                f'<div style="display:flex;align-items:flex-start;'
                f'justify-content:space-between;margin-bottom:5px">'
                f'<div>'
                f'<div style="font-size:14px;font-weight:500;'
                f'color:var(--color-text-primary);line-height:1.2">{modelo}</div>'
                f'<div style="font-size:11px;color:var(--color-text-secondary);'
                f'margin-top:1px">Equipo perforación</div>'
                f'</div>'
                f'<div style="font-size:18px;font-weight:500;'
                f'color:{color};line-height:1">#{numero}</div>'
                f'</div>'
                f'<div style="font-size:11px;color:var(--color-text-secondary);'
                f'margin-bottom:6px">{operador}</div>'
                f'<div style="margin-bottom:8px">{tipos_html}</div>'
                f'</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;'
                f'border-top:0.5px solid var(--color-border-tertiary);'
                f'border-left:0.5px solid var(--color-border-tertiary)">'
                f'<div style="padding:8px 10px;'
                f'border-right:0.5px solid var(--color-border-tertiary);'
                f'border-bottom:0.5px solid var(--color-border-tertiary)">'
                f'<div style="font-size:15px;font-weight:500;color:{color}">{metros:,.1f} m</div>'
                f'<div style="font-size:10px;color:var(--color-text-secondary);'
                f'text-transform:uppercase;letter-spacing:.04em;margin-top:1px">Metros</div>'
                f'</div>'
                f'<div style="padding:8px 10px;'
                f'border-right:0.5px solid var(--color-border-tertiary);'
                f'border-bottom:0.5px solid var(--color-border-tertiary)">'
                f'<div style="font-size:15px;font-weight:500;'
                f'color:var(--color-text-primary)">{pozos}</div>'
                f'<div style="font-size:10px;color:var(--color-text-secondary);'
                f'text-transform:uppercase;letter-spacing:.04em;margin-top:1px">Pozos</div>'
                f'</div>'
                f'<div style="padding:8px 10px;'
                f'border-right:0.5px solid var(--color-border-tertiary)">'
                f'<div style="font-size:15px;font-weight:500;'
                f'color:var(--color-text-primary)">{rend}</div>'
                f'<div style="font-size:10px;color:var(--color-text-secondary);'
                f'text-transform:uppercase;letter-spacing:.04em;margin-top:1px">m/pozo</div>'
                f'</div>'
                f'<div style="padding:8px 10px;'
                f'border-right:0.5px solid var(--color-border-tertiary)">'
                f'<div style="font-size:15px;font-weight:500;'
                f'color:var(--color-text-primary)">{dias}</div>'
                f'<div style="font-size:10px;color:var(--color-text-secondary);'
                f'text-transform:uppercase;letter-spacing:.04em;margin-top:1px">Turnos</div>'
                f'</div>'
                f'</div>'
                f'<div style="padding:8px 12px;display:flex;'
                f'align-items:center;justify-content:space-between;gap:8px">'
                f'<span style="font-size:11px;color:var(--color-text-secondary);'
                f'white-space:nowrap">'
                f'<span style="display:inline-block;width:7px;height:7px;'
                f'border-radius:50%;background:{turno_color};'
                f'margin-right:3px;vertical-align:middle"></span>'
                f'{turno_label}</span>'
                f'<div style="height:3px;background:var(--color-border-tertiary);'
                f'border-radius:2px;flex:1;overflow:hidden">'
                f'<div style="height:100%;width:{min(aporte, 100)}%;'
                f'background:{color};border-radius:2px"></div>'
                f'</div>'
                f'<span style="font-size:11px;font-weight:500;color:{color};'
                f'min-width:36px;text-align:right">{aporte}%</span>'
                f'</div>'
                f'</div>'
            )

            with cols[idx % n_cols]:
                app.st.markdown(html, unsafe_allow_html=True)

            if (idx + 1) % n_cols == 0 and idx < len(equipos) - 1:
                cols = app.st.columns(n_cols)

    # ── Tendencia por fecha ───────────────────────────
    tendencia = obtener_tendencia_malla(banco_sel, fase_sel, malla_sel)
    if tendencia:
        app.st.markdown("---")
        app.st.subheader("Tendencia de avance por fecha")

        import plotly.express as px

        df_tend = pd.DataFrame(tendencia, columns=[
            "Fecha", "Turno", "Pozos", "Metros", "Operadores"
        ])
        df_tend = df_tend.sort_values("Fecha")
        df_tend["Pozos_acum"] = df_tend["Pozos"].cumsum()

        COLOR_TURNO = {
            "Dia": "#D97706", "Día": "#D97706", "dia": "#D97706",
            "Noche": "#3949AB", "noche": "#3949AB",
        }

        col_g1, col_g2 = app.st.columns(2)
        with col_g1:
            app.st.caption("Pozos perforados por fecha y turno")
            fig1 = px.bar(
                df_tend,
                x="Fecha", y="Pozos", color="Turno",
                color_discrete_map=COLOR_TURNO,
                labels={"Pozos": "Pozos perforados", "Fecha": "Fecha turno"},
                height=280,
            )
            fig1.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaed",
                legend_title_text="Turno",
                margin=dict(t=20, b=20, l=20, r=20),
            )
            fig1.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
            fig1.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
            app.st.plotly_chart(fig1, width="stretch")

        with col_g2:
            app.st.caption("Acumulado de pozos perforados")
            fig2 = px.line(
                df_tend,
                x="Fecha", y="Pozos_acum",
                markers=True,
                labels={"Pozos_acum": "Pozos acumulados", "Fecha": "Fecha turno"},
                height=280,
                color_discrete_sequence=["#E67E22"],
            )
            if total_plan > 0:
                fig2.add_hline(
                    y=total_plan,
                    line_dash="dash",
                    line_color="#4caf50",
                    annotation_text=f"Meta: {total_plan} pozos",
                    annotation_font_color="#4caf50",
                )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaed",
                margin=dict(t=20, b=20, l=20, r=20),
            )
            fig2.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
            fig2.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
            app.st.plotly_chart(fig2, width="stretch")

        with app.st.expander("Ver tabla de tendencia", expanded=False):
            app.st.dataframe(
                dataframe_visible(df_tend.drop(columns=["Pozos_acum"])),
                hide_index=True, width="stretch",
            )

    # ── Ranking de operadores ─────────────────────────
    ranking = obtener_ranking_operadores_malla(banco_sel, fase_sel, malla_sel)
    if ranking:
        app.st.markdown("---")
        app.st.subheader("Ranking de operadores en la malla")

        df_rank = pd.DataFrame(ranking, columns=[
            "Operador", "Turno", "Equipo",
            "Pozos", "Metros", "Días trabajados", "Registros",
        ])
        df_rank["Pozos"] = df_rank["Pozos"].fillna(0).astype(int)
        df_rank["Metros"] = df_rank["Metros"].fillna(0.0).round(1)

        col_r1, col_r2 = app.st.columns([3, 2])
        with col_r1:
            app.st.dataframe(
                dataframe_visible(df_rank),
                hide_index=True, width="stretch",
            )
        with col_r2:
            app.st.caption("Pozos por operador")
            import plotly.express as px
            fig_rank = px.bar(
                df_rank.head(10),
                x="Pozos", y="Operador",
                orientation="h",
                color="Turno",
                color_discrete_map={
                    "Dia": "#D97706", "Día": "#D97706", "dia": "#D97706",
                    "Noche": "#3949AB", "noche": "#3949AB",
                },
                height=max(200, len(df_rank.head(10)) * 36),
                labels={"Pozos": "Pozos perforados"},
            )
            fig_rank.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaed",
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            fig_rank.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
            app.st.plotly_chart(fig_rank, width="stretch")

    # ── Resumen todas las mallas ──────────────────────
    app.st.markdown("---")
    app.st.subheader("Resumen general de todas las mallas")
    df_todas = pd.DataFrame(mallas, columns=[
        "Banco", "Fase", "Malla", "Pozos",
        "Metros", "Operadores", "Turnos", "Equipos"
    ])
    df_todas["Malla"] = df_todas["Malla"].astype(str)
    df_todas["Pozos"] = df_todas["Pozos"].astype(int)
    df_todas["Metros"] = df_todas["Metros"].round(1)
    df_todas = df_todas.sort_values(
        ["Banco", "Fase", "Malla"]).reset_index(drop=True)
    app.st.dataframe(
        dataframe_visible(df_todas),
        hide_index=True, width="stretch")


main()
