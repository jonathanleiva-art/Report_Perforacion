from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import base64
import io
import json

import streamlit.components.v1 as components
from PIL import Image, ImageDraw

import app_perforacion as app
from services import ortomosaico_service
from ui import ortomosaico_ui
from ui.components import section_header
from ui.page_header import render_page_header


ORTOMOSAICOS_DIR = ROOT_DIR / "ortomosaicos"
POSICIONES_PATH = ROOT_DIR / "data" / "posiciones_equipos_mapa.json"
ZONAS_PATH = ROOT_DIR / "data" / "zonas_mapa.json"


def cargar_posiciones_equipos():
    if POSICIONES_PATH.exists():
        try:
            return json.loads(POSICIONES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def guardar_posiciones_equipos(posiciones):
    POSICIONES_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSICIONES_PATH.write_text(
        json.dumps(posiciones, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def cargar_zonas():
    if ZONAS_PATH.exists():
        try:
            return json.loads(ZONAS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def guardar_zonas(zonas):
    ZONAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ZONAS_PATH.write_text(
        json.dumps(zonas, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _obtener_equipos_activos():
    return [
        {"modelo": str(modelo), "numero": str(numero)}
        for modelo, numero in app.equipos_esperados()
    ]


def _render_plano_pdf(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    return pix.tobytes("png")


def generar_imagen_con_equipos(ruta_preview, posiciones, equipos_info):
    img = Image.open(ruta_preview).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    r = max(16, min(w, h) // 55)

    for numero, pos in posiciones.items():
        x = int(float(pos["x"]) / 100 * w)
        y = int(float(pos["y"]) / 100 * h)
        eq = next((e for e in equipos_info if str(e["numero"]) == str(numero)), {})

        draw.ellipse([x - r, y - r, x + r, y + r], fill=(249, 115, 22), outline=(255, 255, 255), width=2)

        texto = str(numero)[-4:]
        try:
            draw.text((x, y), texto, fill=(255, 255, 255), anchor="mm")
        except TypeError:
            draw.text((x - r // 2, y - r // 2), texto, fill=(255, 255, 255))

        label = f"{eq.get('modelo', '')} {numero}".strip()
        lw = max(len(label) * 6, 60)
        draw.rectangle([x - lw // 2, y + r + 2, x + lw // 2, y + r + 15], fill=(0, 0, 0))
        try:
            draw.text((x, y + r + 8), label, fill=(255, 255, 255), anchor="mm")
        except TypeError:
            draw.text((x - lw // 2 + 2, y + r + 2), label, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf


def _generar_html_fullscreen_desde_bytes(img_bytes, titulo, mime="png"):
    """HTML standalone con zoom/pan para abrir en pestaña del navegador."""
    b64 = base64.b64encode(img_bytes).decode("ascii")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#000; overflow:hidden; width:100vw; height:100vh; }}
  #container {{
    width:100vw; height:100vh;
    display:flex; align-items:center; justify-content:center;
    overflow:hidden; cursor:grab;
  }}
  #container:active {{ cursor:grabbing; }}
  img {{
    max-width:none; transform-origin:center center;
    user-select:none; -webkit-user-drag:none; display:block;
  }}
  #info {{
    position:fixed; bottom:16px; left:50%; transform:translateX(-50%);
    background:rgba(0,0,0,0.75); color:white; padding:6px 18px;
    border-radius:20px; font-family:system-ui,sans-serif; font-size:12px;
    pointer-events:none; white-space:nowrap;
    border:1px solid rgba(255,255,255,0.15);
  }}
  #titulo {{
    position:fixed; top:14px; left:16px;
    color:rgba(255,255,255,0.85); font-family:system-ui,sans-serif;
    font-size:15px; font-weight:600; text-shadow:0 1px 4px rgba(0,0,0,0.8);
  }}
  #controls {{ position:fixed; top:10px; right:12px; display:flex; gap:8px; }}
  #controls button {{
    background:rgba(0,0,0,0.75); color:white;
    border:1px solid rgba(255,255,255,0.25);
    padding:6px 14px; border-radius:6px; cursor:pointer; font-size:13px;
    transition:background 0.15s;
  }}
  #controls button:hover {{ background:rgba(255,255,255,0.18); }}
</style>
</head>
<body>
<div id="container">
  <img id="img" src="data:image/{mime};base64,{b64}" draggable="false"/>
</div>
<div id="titulo">{titulo}</div>
<div id="info">Rueda del mouse para zoom &middot; Arrastra para mover &middot; Doble clic para centrar</div>
<div id="controls">
  <button onclick="resetView()">&#8962; Restablecer</button>
  <button onclick="document.documentElement.requestFullscreen && document.documentElement.requestFullscreen()">&#9974; Pantalla completa</button>
</div>
<script>
const img = document.getElementById('img');
const container = document.getElementById('container');
let scale = 1, tx = 0, ty = 0, dragging = false;
let startX, startY, startTx, startTy;

function applyTransform() {{
  img.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
}}

container.addEventListener('wheel', e => {{
  e.preventDefault();
  scale = Math.min(Math.max(scale * (e.deltaY > 0 ? 0.9 : 1.1), 0.05), 30);
  applyTransform();
}}, {{ passive: false }});

container.addEventListener('mousedown', e => {{
  dragging = true;
  startX = e.clientX; startY = e.clientY;
  startTx = tx; startTy = ty;
}});
window.addEventListener('mousemove', e => {{
  if (!dragging) return;
  tx = startTx + (e.clientX - startX);
  ty = startTy + (e.clientY - startY);
  applyTransform();
}});
window.addEventListener('mouseup', () => {{ dragging = false; }});
container.addEventListener('dblclick', () => resetView());

function resetView() {{
  scale = Math.min(window.innerWidth / img.naturalWidth, window.innerHeight / img.naturalHeight) * 0.98;
  tx = 0; ty = 0;
  applyTransform();
}}

img.onload = () => resetView();
</script>
</body>
</html>"""


def _generar_editor_fullscreen_html(orto_bytes, equipos, posiciones):
    """Editor drag & drop standalone fullscreen con pan/zoom #world."""
    b64_img = base64.b64encode(orto_bytes).decode("ascii")
    equipos_json = json.dumps(equipos, ensure_ascii=False)
    posiciones_json = json.dumps(posiciones, ensure_ascii=False)

    return (
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Editor de equipos - Pantalla completa</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#111; display:flex; flex-direction:column; width:100vw; height:100vh; overflow:hidden; font-family:sans-serif; color:white; }
#top-bar {
    height:44px; background:#1a1a2e; display:flex; align-items:center;
    padding:0 12px; gap:10px; flex-shrink:0;
    border-bottom:1px solid rgba(255,255,255,0.1); overflow-x:auto;
}
#top-bar h3 { color:white; font-size:13px; font-weight:500; margin-right:8px; flex-shrink:0; }
.chip {
    background:#1e40af; color:white; padding:5px 12px;
    border-radius:20px; font-size:12px; cursor:grab;
    border:1px solid rgba(255,255,255,0.15); white-space:nowrap; flex-shrink:0;
    user-select:none;
}
.chip:hover { background:#2563eb; }
.chip:active { cursor:grabbing; background:#f97316; }
#viewport { flex:1; position:relative; overflow:hidden; background:#000; cursor:grab; }
#viewport.panning { cursor:grabbing; }
#world { position:absolute; top:0; left:0; transform-origin:0 0; }
#world img { display:block; max-width:none; user-select:none; -webkit-user-drag:none; pointer-events:none; }
.eq-icon {
    position:absolute; background:#f97316; color:white;
    border-radius:50%; width:38px; height:38px;
    display:flex; align-items:center; justify-content:center;
    font-size:12px; font-weight:bold; cursor:grab;
    border:2px solid white; box-shadow:0 2px 8px rgba(0,0,0,0.7);
    transform:translate(-50%,-50%); z-index:10; user-select:none;
}
.eq-icon:active { cursor:grabbing; }
.eq-label {
    position:absolute; background:rgba(0,0,0,0.82); color:white;
    font-size:11px; padding:2px 7px; border-radius:4px;
    white-space:nowrap; transform:translate(-50%,14px);
    z-index:11; pointer-events:none;
}
#bottom-bar {
    height:40px; background:rgba(0,0,0,0.88);
    display:flex; align-items:center; padding:0 14px; gap:10px;
    border-top:1px solid rgba(255,255,255,0.1); flex-shrink:0;
}
#zoom-label { color:rgba(255,255,255,0.5); font-size:11px; min-width:60px; font-family:monospace; }
#json-display { flex:1; color:#22c55e; font-family:monospace; font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.btn { background:#1e40af; color:white; border:none; padding:5px 14px; border-radius:6px; cursor:pointer; font-size:12px; flex-shrink:0; }
.btn:hover { background:#2563eb; }
.btn-green { background:#166534; }
.btn-green:hover { background:#15803d; }
#hint-text { color:rgba(255,255,255,0.3); font-size:10px; flex-shrink:0; }
</style>
</head>
<body>
<div id="top-bar">
  <h3>&#9935; Equipos &rarr;</h3>
</div>
<div id="viewport">
  <div id="world">
    <img id="orto" src="data:image/jpeg;base64,""" + b64_img + """" draggable="false"/>
  </div>
</div>
<div id="bottom-bar">
  <span id="zoom-label">100%</span>
  <span id="json-display">Sin equipos colocados</span>
  <button class="btn" onclick="copiarJSON()">Copiar JSON</button>
  <button class="btn btn-green" onclick="descargarImagen()">Descargar PNG</button>
  <span id="hint-text">Rueda=zoom &middot; Arrastrar=mover &middot; Dbl.clic fondo=centrar &middot; Dbl.clic &iacute;cono=eliminar</span>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script>
const EQUIPOS = """ + equipos_json + """;
const POS_INIT = """ + posiciones_json + """;
const viewport = document.getElementById('viewport');
const world    = document.getElementById('world');
const orto     = document.getElementById('orto');
const topBar   = document.getElementById('top-bar');
let camX=0, camY=0, camScale=1;
let isPanning=false, panSX=0, panSY=0, panCX=0, panCY=0;
let posiciones = Object.assign({}, POS_INIT);

EQUIPOS.forEach(eq => {
    const chip = document.createElement('div');
    chip.className = 'chip';
    chip.textContent = eq.modelo + ' ' + eq.numero;
    chip.draggable = true;
    chip.addEventListener('dragstart', e => e.dataTransfer.setData('equipo', JSON.stringify(eq)));
    topBar.appendChild(chip);
});

function applyCamera() {
    world.style.transform = 'translate('+camX+'px,'+camY+'px) scale('+camScale+')';
    document.getElementById('zoom-label').textContent = Math.round(camScale*100)+'%';
}
function resetCam() {
    const vw=viewport.clientWidth, vh=viewport.clientHeight;
    const iw=orto.naturalWidth||800, ih=orto.naturalHeight||600;
    camScale=Math.min(vw/iw, vh/ih)*0.95;
    camX=(vw-iw*camScale)/2; camY=(vh-ih*camScale)/2; applyCamera();
}
viewport.addEventListener('wheel', e => {
    e.preventDefault();
    const rect=viewport.getBoundingClientRect();
    const mx=e.clientX-rect.left, my=e.clientY-rect.top;
    const ns=Math.min(Math.max(camScale*(e.deltaY>0?0.85:1.18),0.05),20);
    camX=mx-(mx-camX)*(ns/camScale); camY=my-(my-camY)*(ns/camScale);
    camScale=ns; applyCamera();
}, {passive:false});
viewport.addEventListener('mousedown', e => {
    if (e.target.closest('.eq-icon')) return;
    isPanning=true; panSX=e.clientX; panSY=e.clientY; panCX=camX; panCY=camY;
    viewport.classList.add('panning');
});
window.addEventListener('mousemove', e => {
    if (!isPanning) return;
    camX=panCX+(e.clientX-panSX); camY=panCY+(e.clientY-panSY); applyCamera();
});
window.addEventListener('mouseup', ()=>{ isPanning=false; viewport.classList.remove('panning'); });
viewport.addEventListener('dblclick', e => {
    const icon=e.target.closest('.eq-icon');
    if (icon) {
        const eq=JSON.parse(icon.dataset.equipo);
        icon.remove(); document.getElementById('label-'+eq.numero)?.remove();
        delete posiciones[eq.numero]; actualizarDisplay();
    } else { resetCam(); }
});
viewport.addEventListener('dragover', e=>e.preventDefault());
viewport.addEventListener('drop', e => {
    e.preventDefault();
    const raw=e.dataTransfer.getData('equipo'); if(!raw) return;
    const eq=JSON.parse(raw);
    const rect=viewport.getBoundingClientRect();
    const worldX=(e.clientX-rect.left-camX)/camScale;
    const worldY=(e.clientY-rect.top-camY)/camScale;
    const iw=orto.naturalWidth||800, ih=orto.naturalHeight||600;
    const xPct=parseFloat((worldX/iw*100).toFixed(2));
    const yPct=parseFloat((worldY/ih*100).toFixed(2));
    posiciones[String(eq.numero)]={x:xPct,y:yPct};
    colocarIcono(eq,xPct,yPct); actualizarDisplay();
});
function colocarIcono(eq,xPct,yPct) {
    const num=String(eq.numero);
    document.getElementById('icon-'+num)?.remove();
    document.getElementById('label-'+num)?.remove();
    const iw=orto.naturalWidth||800, ih=orto.naturalHeight||600;
    const px=parseFloat(xPct)/100*iw, py=parseFloat(yPct)/100*ih;
    const icon=document.createElement('div');
    icon.className='eq-icon'; icon.id='icon-'+num;
    icon.textContent=num.slice(-4);
    icon.style.left=px+'px'; icon.style.top=py+'px';
    icon.draggable=true; icon.dataset.equipo=JSON.stringify(eq);
    icon.title=eq.modelo+' '+num+' — doble clic para eliminar';
    icon.addEventListener('dragstart',e=>e.dataTransfer.setData('equipo',JSON.stringify(eq)));
    world.appendChild(icon);
    const label=document.createElement('div');
    label.className='eq-label'; label.id='label-'+num;
    label.style.left=px+'px'; label.style.top=py+'px';
    label.textContent=eq.modelo+' '+num;
    world.appendChild(label);
}
function actualizarDisplay() {
    const n=Object.keys(posiciones).length;
    document.getElementById('json-display').textContent=n?JSON.stringify(posiciones):'Sin equipos colocados';
}
function copiarJSON() {
    const texto=JSON.stringify(posiciones,null,2);
    const ok=()=>alert('JSON copiado — pégalo en el sistema para guardar.');
    navigator.clipboard?.writeText?.(texto).then(ok).catch(()=>_fb(texto,ok))||_fb(texto,ok);
}
function _fb(txt,cb){
    const ta=document.createElement('textarea');
    ta.value=txt; ta.style.cssText='position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta); ta.select();
    try{document.execCommand('copy');}catch(e){}
    document.body.removeChild(ta); cb();
}
function descargarImagen() {
    if(typeof html2canvas==='undefined'){alert('html2canvas no cargó');return;}
    html2canvas(world,{useCORS:true,scale:1.5,backgroundColor:'#000'}).then(canvas=>{
        const a=document.createElement('a');
        a.download='mina_equipos_'+new Date().toISOString().slice(0,10)+'.png';
        a.href=canvas.toDataURL('image/png'); a.click();
    });
}
function renderInit() {
    Object.entries(POS_INIT).forEach(([num,p])=>{
        const eq=EQUIPOS.find(e=>String(e.numero)===String(num));
        if(eq) colocarIcono(eq,parseFloat(p.x),parseFloat(p.y));
    });
    actualizarDisplay();
}
if(orto.complete&&orto.naturalWidth){resetCam();renderInit();}
else{orto.onload=()=>{resetCam();renderInit();};}
</script>
</body>
</html>"""
    )


def _generar_editor_completo_html(orto_bytes, equipos, posiciones_equipos, zonas):
    b64_img = base64.b64encode(orto_bytes).decode("ascii")
    equipos_json = json.dumps(equipos, ensure_ascii=False)
    posiciones_json = json.dumps(posiciones_equipos, ensure_ascii=False)
    zonas_json = json.dumps(zonas, ensure_ascii=False)

    return (
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#111; display:flex; flex-direction:column; width:100%; height:720px; font-family:sans-serif; overflow:hidden; }

#toolbar {
    background:#1a1a2e; display:flex; align-items:center;
    padding:6px 12px; gap:6px; flex-shrink:0; flex-wrap:wrap;
    border-bottom:1px solid rgba(255,255,255,0.10); min-height:48px;
}
#toolbar .sep { width:1px; height:24px; background:rgba(255,255,255,0.15); margin:0 4px; flex-shrink:0; }
#toolbar label { color:rgba(255,255,255,0.55); font-size:11px; white-space:nowrap; }

.btn {
    background:rgba(255,255,255,0.08); color:white;
    border:1px solid rgba(255,255,255,0.15);
    padding:5px 11px; border-radius:6px; cursor:pointer; font-size:12px; white-space:nowrap;
}
.btn:hover { background:rgba(255,255,255,0.16); }
.btn.active { background:#1e40af; border-color:#3b82f6; }
.btn-red   { background:rgba(239,68,68,0.18); border-color:rgba(239,68,68,0.35); }
.btn-red:hover { background:rgba(239,68,68,0.30); }
.btn-green { background:rgba(22,163,74,0.22); border-color:rgba(22,163,74,0.45); }
.btn-green:hover { background:rgba(22,163,74,0.35); }

#color-zona { width:30px; height:26px; border:none; border-radius:4px; cursor:pointer; padding:1px; }
#zona-nombre {
    background:rgba(255,255,255,0.08); color:white;
    border:1px solid rgba(255,255,255,0.15); padding:4px 8px;
    border-radius:6px; font-size:12px; width:130px;
}
#zona-nombre::placeholder { color:rgba(255,255,255,0.30); }

#viewport { flex:1; position:relative; overflow:hidden; background:#000; cursor:grab; }
#viewport.cursor-draw { cursor:crosshair; }
#viewport.cursor-grab { cursor:grabbing; }

#world { position:absolute; top:0; left:0; transform-origin:0 0; }
#world img { display:block; max-width:none; user-select:none; -webkit-user-drag:none; }

#svg-overlay { position:absolute; top:0; left:0; overflow:visible; pointer-events:none; }
#svg-overlay.drawing { pointer-events:all; }

.eq-icon {
    position:absolute; background:#f97316; color:white;
    border-radius:50%; width:36px; height:36px;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:bold; cursor:grab;
    border:2px solid white; box-shadow:0 2px 8px rgba(0,0,0,0.7);
    transform:translate(-50%,-50%); z-index:20; user-select:none;
}
.eq-icon:hover { box-shadow:0 4px 16px rgba(249,115,22,0.6); }
.eq-icon:active { cursor:grabbing; }
.eq-label {
    position:absolute; background:rgba(0,0,0,0.80); color:white;
    font-size:10px; padding:2px 6px; border-radius:4px;
    white-space:nowrap; transform:translate(-50%,14px);
    z-index:21; pointer-events:none;
}

#bottom-panel {
    background:#0f0f1a; border-top:1px solid rgba(255,255,255,0.08);
    flex-shrink:0; display:flex; flex-direction:column;
}
#equipos-chips {
    display:flex; align-items:center; gap:6px; padding:6px 12px;
    flex-wrap:wrap; border-bottom:0.5px solid rgba(255,255,255,0.06); min-height:38px;
}
#equipos-chips span.lbl { color:rgba(255,255,255,0.45); font-size:11px; margin-right:4px; flex-shrink:0; }
.eq-chip {
    background:#1e3a6e; color:white; padding:4px 10px;
    border-radius:14px; font-size:11px; cursor:grab;
    border:1px solid rgba(255,255,255,0.12); white-space:nowrap; user-select:none;
}
.eq-chip:hover { background:#2563eb; }
.eq-chip:active { cursor:grabbing; }

#zonas-lista {
    display:flex; align-items:center; gap:6px; padding:5px 12px;
    flex-wrap:wrap; min-height:34px;
}
#zonas-lista span.lbl { color:rgba(255,255,255,0.45); font-size:11px; margin-right:4px; flex-shrink:0; }
.zona-pill {
    display:flex; align-items:center; gap:5px;
    background:rgba(255,255,255,0.06); border:0.5px solid rgba(255,255,255,0.12);
    border-radius:12px; padding:3px 8px; font-size:11px; color:white;
}
.zona-swatch { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.zona-del { cursor:pointer; color:rgba(239,68,68,0.6); margin-left:3px; font-size:13px; line-height:1; }
.zona-del:hover { color:#ef4444; }

#statusbar {
    height:32px; background:rgba(0,0,0,0.85);
    display:flex; align-items:center; padding:0 12px; gap:12px;
    border-top:1px solid rgba(255,255,255,0.06); flex-shrink:0;
}
#status-txt { flex:1; color:rgba(255,255,255,0.50); font-size:11px; }
#zoom-txt   { color:rgba(255,255,255,0.40); font-size:11px; min-width:44px; }
</style>
</head>
<body>

<div id="toolbar">
  <label>Modo:</label>
  <button class="btn active" id="btn-pan"  onclick="setModo('pan')">&#9997; Mover</button>
  <button class="btn"        id="btn-draw" onclick="setModo('draw')">&#9998; Zona</button>
  <div class="sep"></div>
  <button class="btn btn-red"   onclick="undoPunto()">&#8617; Punto</button>
  <button class="btn btn-green" onclick="cerrarZona()">&#9634; Cerrar zona</button>
  <div class="sep"></div>
  <label>Color:</label>
  <input type="color" id="color-zona" value="#F97316">
  <input type="text"  id="zona-nombre" placeholder="Nombre malla / zona">
  <div class="sep"></div>
  <button class="btn" onclick="copiarJSON()">Copiar JSON</button>
  <button class="btn btn-green" onclick="descargarPNG()">Descargar PNG</button>
</div>

<div id="viewport">
  <div id="world">
    <img id="orto" src="data:image/jpeg;base64,""" + b64_img + """" draggable="false"/>
    <svg id="svg-overlay"></svg>
  </div>
</div>

<div id="bottom-panel">
  <div id="equipos-chips">
    <span class="lbl">&#9935; Equipos &#8594;</span>
  </div>
  <div id="zonas-lista">
    <span class="lbl">&#11041; Zonas &#8594;</span>
  </div>
</div>

<div id="statusbar">
  <span id="status-txt">Modo mover &middot; Arrastra equipos al mapa &middot; Activa &#9998; Zona para dibujar per&iacute;metros</span>
  <span id="zoom-txt">100%</span>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script>
const EQUIPOS    = """ + equipos_json + """;
const POS_INIT   = """ + posiciones_json + """;
const ZONAS_INIT = """ + zonas_json + """;

let posEquipos = Object.assign({}, POS_INIT);
let zonas      = JSON.parse(JSON.stringify(ZONAS_INIT));
let modo       = 'pan';
let puntosTemp = [];
let camX=0, camY=0, camScale=1;
let isPanning=false, pSX=0, pSY=0, pCX=0, pCY=0;

const viewport    = document.getElementById('viewport');
const world       = document.getElementById('world');
const orto        = document.getElementById('orto');
const svgOvl      = document.getElementById('svg-overlay');
const chipsEl     = document.getElementById('equipos-chips');
const zonasListEl = document.getElementById('zonas-lista');
const statusEl    = document.getElementById('status-txt');
const zoomEl      = document.getElementById('zoom-txt');

function imgW() { return orto.naturalWidth  || orto.clientWidth  || 800; }
function imgH() { return orto.naturalHeight || orto.clientHeight || 600; }

function syncSVG() {
    svgOvl.setAttribute('width',  imgW());
    svgOvl.setAttribute('height', imgH());
}
function applyCamera() {
    world.style.transform = `translate(${camX}px,${camY}px) scale(${camScale})`;
    zoomEl.textContent = Math.round(camScale*100)+'%';
    syncSVG();
}
function resetCam() {
    const vw=viewport.clientWidth, vh=viewport.clientHeight;
    camScale = Math.min(vw/imgW(), vh/imgH()) * 0.93;
    camX = (vw - imgW()*camScale) / 2;
    camY = (vh - imgH()*camScale) / 2;
    applyCamera();
}

viewport.addEventListener('wheel', e => {
    e.preventDefault();
    const r=viewport.getBoundingClientRect();
    const mx=e.clientX-r.left, my=e.clientY-r.top;
    const ns=Math.min(Math.max(camScale*(e.deltaY>0?0.85:1.18),0.1),15);
    camX=mx-(mx-camX)*(ns/camScale); camY=my-(my-camY)*(ns/camScale);
    camScale=ns; applyCamera();
}, {passive:false});

viewport.addEventListener('mousedown', e => {
    if (modo!=='pan' || e.target.classList.contains('eq-icon')) return;
    isPanning=true; pSX=e.clientX; pSY=e.clientY; pCX=camX; pCY=camY;
    viewport.classList.add('cursor-grab');
});
window.addEventListener('mousemove', e => {
    if (!isPanning) return;
    camX=pCX+(e.clientX-pSX); camY=pCY+(e.clientY-pSY); applyCamera();
});
window.addEventListener('mouseup', () => { isPanning=false; viewport.classList.remove('cursor-grab'); });
viewport.addEventListener('dblclick', e => {
    if (modo==='pan' && !e.target.classList.contains('eq-icon')) resetCam();
});

function setModo(m) {
    modo = m;
    document.getElementById('btn-pan').classList.toggle('active',  m==='pan');
    document.getElementById('btn-draw').classList.toggle('active', m==='draw');
    svgOvl.classList.toggle('drawing', m==='draw');
    viewport.classList.toggle('cursor-draw', m==='draw');
    statusEl.textContent = m==='pan'
        ? 'Modo mover · Arrastra equipos al mapa · Doble clic = centrar'
        : 'Modo zona · Clic = agregar punto · "Cerrar zona" para terminar';
}

// ── Equipos ──────────────────────────────────────────────────────────
EQUIPOS.forEach(eq => {
    const chip = document.createElement('div');
    chip.className = 'eq-chip';
    chip.textContent = eq.modelo + ' ' + eq.numero;
    chip.draggable = true;
    chip.addEventListener('dragstart', e => e.dataTransfer.setData('equipo', JSON.stringify(eq)));
    chipsEl.appendChild(chip);
});

viewport.addEventListener('dragover', e => e.preventDefault());
viewport.addEventListener('drop', e => {
    e.preventDefault();
    const data = e.dataTransfer.getData('equipo'); if (!data) return;
    const eq = JSON.parse(data);
    const r = viewport.getBoundingClientRect();
    const wx = (e.clientX - r.left - camX) / camScale;
    const wy = (e.clientY - r.top  - camY) / camScale;
    const xPct = parseFloat((wx / imgW() * 100).toFixed(2));
    const yPct = parseFloat((wy / imgH() * 100).toFixed(2));
    posEquipos[String(eq.numero)] = {x: xPct, y: yPct};
    colocarIcono(eq, xPct, yPct);
    actualizarJSON();
});

function colocarIcono(eq, xPct, yPct) {
    const num = String(eq.numero);
    document.getElementById('icon-'+num)?.remove();
    document.getElementById('label-'+num)?.remove();
    const px = parseFloat(xPct)/100 * imgW();
    const py = parseFloat(yPct)/100 * imgH();

    const icon = document.createElement('div');
    icon.className = 'eq-icon'; icon.id = 'icon-'+num;
    icon.textContent = num.slice(-4);
    icon.style.left = px+'px'; icon.style.top = py+'px';
    icon.draggable = true;
    icon.title = eq.modelo+' '+num+' — doble clic para eliminar';
    icon.addEventListener('dragstart', e => e.dataTransfer.setData('equipo', JSON.stringify(eq)));
    icon.addEventListener('dblclick', e => {
        e.stopPropagation();
        icon.remove();
        document.getElementById('label-'+num)?.remove();
        delete posEquipos[num]; actualizarJSON();
    });
    world.appendChild(icon);

    const lbl = document.createElement('div');
    lbl.className = 'eq-label'; lbl.id = 'label-'+num;
    lbl.style.left = px+'px'; lbl.style.top = py+'px';
    lbl.textContent = eq.modelo+' '+eq.numero;
    world.appendChild(lbl);
}

// ── Zonas ────────────────────────────────────────────────────────────
svgOvl.addEventListener('click', e => {
    if (modo!=='draw') return;
    // getBoundingClientRect devuelve coords de pantalla (escaladas por camScale).
    // Se divide por camScale para obtener coordenadas internas del SVG (= px naturales).
    const r = svgOvl.getBoundingClientRect();
    const px = (e.clientX - r.left) / camScale;
    const py = (e.clientY - r.top)  / camScale;
    puntosTemp.push({x: px, y: py});
    renderTemp();
    statusEl.textContent = `Puntos: ${puntosTemp.length} · "Cerrar zona" para terminar · ↩ deshacer`;
});

function renderTemp() {
    svgOvl.querySelectorAll('.tmp').forEach(el => el.remove());
    if (!puntosTemp.length) return;
    const color = document.getElementById('color-zona').value;
    if (puntosTemp.length >= 2) {
        const pl = document.createElementNS('http://www.w3.org/2000/svg','polyline');
        pl.setAttribute('points', puntosTemp.map(p => p.x+','+p.y).join(' '));
        pl.setAttribute('fill', hexAlpha(color, 0.15));
        pl.setAttribute('stroke', color);
        pl.setAttribute('stroke-width', '2.5');
        pl.setAttribute('stroke-dasharray', '6,3');
        pl.classList.add('tmp'); svgOvl.appendChild(pl);
    }
    puntosTemp.forEach((p, i) => {
        const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
        c.setAttribute('cx', p.x); c.setAttribute('cy', p.y);
        c.setAttribute('r', i===0 ? 6 : 4);
        c.setAttribute('fill', i===0 ? color : 'white');
        c.setAttribute('stroke', color); c.setAttribute('stroke-width','1.5');
        c.classList.add('tmp'); svgOvl.appendChild(c);
    });
}

function undoPunto() { puntosTemp.pop(); renderTemp(); }

function cerrarZona() {
    if (puntosTemp.length < 3) { alert('Necesitas al menos 3 puntos.'); return; }
    const nombre = document.getElementById('zona-nombre').value.trim() || ('Zona '+(zonas.length+1));
    const color  = document.getElementById('color-zona').value;
    const puntos = puntosTemp.map(p => ({
        x: (p.x / imgW() * 100).toFixed(2),
        y: (p.y / imgH() * 100).toFixed(2),
    }));
    zonas.push({id: Date.now(), nombre, color, puntos});
    puntosTemp = [];
    document.getElementById('zona-nombre').value = '';
    svgOvl.querySelectorAll('.tmp').forEach(el => el.remove());
    renderZonas(); renderZonasList(); actualizarJSON();
    statusEl.textContent = `"${nombre}" guardada · Sigue dibujando o copia el JSON`;
}

function renderZonas() {
    svgOvl.querySelectorAll('.zona-svg').forEach(el => el.remove());
    zonas.forEach(z => {
        const pts = z.puntos.map(p => `${p.x/100*imgW()},${p.y/100*imgH()}`).join(' ');
        const g = document.createElementNS('http://www.w3.org/2000/svg','g');
        g.classList.add('zona-svg');

        const poly = document.createElementNS('http://www.w3.org/2000/svg','polygon');
        poly.setAttribute('points', pts);
        poly.setAttribute('fill', hexAlpha(z.color, 0.20));
        poly.setAttribute('stroke', z.color);
        poly.setAttribute('stroke-width', '2.5');
        g.appendChild(poly);

        const cx = z.puntos.reduce((s,p) => s+parseFloat(p.x), 0)/z.puntos.length/100*imgW();
        const cy = z.puntos.reduce((s,p) => s+parseFloat(p.y), 0)/z.puntos.length/100*imgH();
        const tw = z.nombre.length*7+10;
        const bg = document.createElementNS('http://www.w3.org/2000/svg','rect');
        bg.setAttribute('x', cx-tw/2); bg.setAttribute('y', cy-12);
        bg.setAttribute('width', tw);  bg.setAttribute('height', 19);
        bg.setAttribute('rx', '4');    bg.setAttribute('fill','rgba(0,0,0,0.75)');
        g.appendChild(bg);

        const txt = document.createElementNS('http://www.w3.org/2000/svg','text');
        txt.setAttribute('x', cx); txt.setAttribute('y', cy+4);
        txt.setAttribute('text-anchor','middle');
        txt.setAttribute('font-size','12'); txt.setAttribute('font-weight','700');
        txt.setAttribute('fill', z.color); txt.setAttribute('font-family','sans-serif');
        txt.textContent = z.nombre;
        g.appendChild(txt);
        svgOvl.appendChild(g);
    });
}

function renderZonasList() {
    const lbl = zonasListEl.querySelector('span.lbl');
    zonasListEl.innerHTML = ''; zonasListEl.appendChild(lbl);
    if (!zonas.length) {
        const em = document.createElement('span');
        em.style.cssText = 'color:rgba(255,255,255,0.30);font-size:11px;';
        em.textContent = 'Sin zonas'; zonasListEl.appendChild(em); return;
    }
    zonas.forEach((z, i) => {
        const pill = document.createElement('div');
        pill.className = 'zona-pill';
        pill.innerHTML = `<div class="zona-swatch" style="background:${z.color}"></div>`
            + `<span>${z.nombre}</span>`
            + `<span class="zona-del" onclick="eliminarZona(${i})">&#10005;</span>`;
        zonasListEl.appendChild(pill);
    });
}

function eliminarZona(i) {
    zonas.splice(i, 1); renderZonas(); renderZonasList(); actualizarJSON();
}

// ── JSON & export ─────────────────────────────────────────────────────
function hexAlpha(hex, a) {
    const r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    return `rgba(${r},${g},${b},${a})`;
}
function actualizarJSON() {
    window._editorJSON = JSON.stringify({equipos: posEquipos, zonas: zonas});
}
function copiarJSON() {
    actualizarJSON();
    const txt = window._editorJSON || '{}';
    const ok = () => alert('JSON copiado — pégalo en el campo de abajo para guardar');
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(txt).then(ok).catch(() => _fbCopy(txt, ok));
    } else { _fbCopy(txt, ok); }
}
function _fbCopy(txt, cb) {
    const ta = document.createElement('textarea');
    ta.value=txt; ta.style.cssText='position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta); cb();
}
function descargarPNG() {
    if (typeof html2canvas==='undefined') { alert('Cargando, intenta en 2 segundos'); return; }
    html2canvas(world, {useCORS:true, scale:1.5, backgroundColor:'#000'}).then(c => {
        const a = document.createElement('a');
        a.download = 'mina_'+new Date().toISOString().slice(0,10)+'.png';
        a.href = c.toDataURL('image/png'); a.click();
    });
}

// ── Init ──────────────────────────────────────────────────────────────
function init() {
    syncSVG(); resetCam();
    Object.entries(POS_INIT).forEach(([num, pos]) => {
        const eq = EQUIPOS.find(e => String(e.numero)===String(num));
        if (eq) colocarIcono(eq, parseFloat(pos.x), parseFloat(pos.y));
    });
    renderZonas(); renderZonasList(); actualizarJSON();
}
orto.complete && orto.naturalWidth ? init() : (orto.onload = init);

window.addEventListener('resize', () => { syncSVG(); renderZonas(); });
</script>
</body>
</html>"""
    )


def _mime_desde_ruta(ruta):
    ext = Path(ruta).suffix.lower()
    return "jpeg" if ext in (".jpg", ".jpeg") else "png"


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, "Ortomosaico Vista Mina")
    app.st.caption("Vista referencial de apoyo para ubicación y seguimiento de trabajos de perforación.")
    app.st.markdown(
        """
        <style>
            .main .block-container {
                padding-top: 1rem;
                padding-left: 0.5rem;
                padding-right: 0.5rem;
                max-width: 100%;
            }
            .plotly-graph-div { width: 100% !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    ORTOMOSAICOS_DIR.mkdir(parents=True, exist_ok=True)
    archivos = ortomosaico_service.listar_archivos_ortomosaico(ORTOMOSAICOS_DIR)
    if not archivos:
        app.st.info("No hay archivos de ortomosaico disponibles en la carpeta `ortomosaicos/`.")
        return

    seleccionado = app.st.selectbox(
        "Archivo disponible",
        archivos,
        format_func=lambda ruta: ruta.name,
    )

    try:
        ortomosaico = ortomosaico_service.obtener_ortomosaico(seleccionado)
    except Exception as exc:
        app.st.error(f"No fue posible preparar el ortomosaico: {exc}")
        app.st.code(str(seleccionado))
        return

    ortomosaico_ui.renderizar_controles(app.st, ortomosaico)

    # ── Vista en paralelo ───────────────────────────────────────────────
    app.st.subheader("Vista en paralelo")
    col1, col2 = app.st.columns(2)

    with col1:
        app.st.markdown("#### Ortomosaico")
        app.st.caption("Rueda del mouse para zoom · Arrastre para desplazar · Barra Plotly para resetear/exportar.")
        fig_paralelo = ortomosaico_ui.construir_figura_ortomosaico(ortomosaico, altura=800)
        fig_paralelo.update_layout(
            paper_bgcolor="black",
            plot_bgcolor="black",
            margin=dict(l=0, r=0, t=0, b=0),
        )
        app.st.plotly_chart(
            fig_paralelo,
            use_container_width=True,
            config=ortomosaico_ui.config_plotly_interactivo(),
        )
        orto_preview_bytes = ortomosaico.ruta_preview.read_bytes()
        orto_mime = _mime_desde_ruta(ortomosaico.ruta_preview)
        html_fs_orto = _generar_html_fullscreen_desde_bytes(
            orto_preview_bytes, ortomosaico.nombre, mime=orto_mime
        )
        app.st.download_button(
            label="Abrir ortomosaico en pantalla completa",
            data=html_fs_orto.encode("utf-8"),
            file_name=f"{ortomosaico.ruta_preview.stem}_fullscreen.html",
            mime="text/html",
            key="btn_fs_ortomosaico",
            help="Descarga un HTML — ábrelo en el navegador para zoom libre sin límites",
        )

    with col2:
        app.st.markdown("#### Plano de perforación")
        plano_file = app.st.file_uploader(
            "Cargar plano (JPG/PNG/PDF)",
            type=["jpg", "jpeg", "png", "pdf"],
            key="plano_perforacion",
        )
        if plano_file:
            raw = plano_file.read()
            if plano_file.type == "application/pdf":
                try:
                    datos_plano = _render_plano_pdf(raw)
                    app.st.session_state["plano_guardado_mime"] = "png"
                except Exception as exc:
                    app.st.error(f"No se pudo renderizar el PDF: {exc}")
                    datos_plano = None
            else:
                datos_plano = raw
                _ext = (plano_file.name or "").rsplit(".", 1)[-1].lower()
                app.st.session_state["plano_guardado_mime"] = "jpeg" if _ext in ("jpg", "jpeg") else "png"
            if datos_plano:
                app.st.session_state["plano_guardado"] = datos_plano
                app.st.image(datos_plano, use_container_width=True)
                _mime_p = app.st.session_state.get("plano_guardado_mime", "png")
                html_fs_plano = _generar_html_fullscreen_desde_bytes(
                    datos_plano, "Plano de perforación", mime=_mime_p
                )
                app.st.download_button(
                    label="Abrir plano con zoom completo",
                    data=html_fs_plano.encode("utf-8"),
                    file_name="plano_perforacion_fullscreen.html",
                    mime="text/html",
                    key="btn_fs_plano_nuevo",
                    help="Descarga un HTML — ábrelo en el navegador para zoom libre",
                )
        elif app.st.session_state.get("plano_guardado"):
            _datos_cach = app.st.session_state["plano_guardado"]
            _mime_cach = app.st.session_state.get("plano_guardado_mime", "png")
            app.st.image(_datos_cach, use_container_width=True)
            html_fs_plano_cach = _generar_html_fullscreen_desde_bytes(
                _datos_cach, "Plano de perforación", mime=_mime_cach
            )
            app.st.download_button(
                label="Abrir plano con zoom completo",
                data=html_fs_plano_cach.encode("utf-8"),
                file_name="plano_perforacion_fullscreen.html",
                mime="text/html",
                key="btn_fs_plano_cache",
                help="Descarga un HTML — ábrelo en el navegador para zoom libre",
            )
        else:
            app.st.info("Sube un plano para compararlo con el ortomosaico lado a lado.")

    # ── Editor de mapa — equipos y zonas ────────────────────────────────
    app.st.divider()
    section_header(
        "Editor de mapa — equipos y zonas",
        "Posiciona equipos y dibuja zonas de perforación sobre el ortomosaico",
        kicker="Editor",
        st_module=app.st,
    )
    app.st.caption(
        "Arrastra equipos desde el panel inferior al mapa · "
        "Activa ✏️ Zona para dibujar perímetros · "
        "Copia el JSON → pégalo aquí → Guardar"
    )

    equipos_activos = _obtener_equipos_activos()
    posiciones_equipos = cargar_posiciones_equipos()
    zonas_guardadas = cargar_zonas()

    editor_html = _generar_editor_completo_html(
        orto_preview_bytes, equipos_activos, posiciones_equipos, zonas_guardadas
    )
    components.html(editor_html, height=760, scrolling=False)

    app.st.markdown("##### Guardar cambios del editor")
    app.st.caption("Copia el JSON del toolbar → pégalo aquí → Guardar")
    json_input = app.st.text_area(
        "JSON del editor",
        value=json.dumps({"equipos": posiciones_equipos, "zonas": zonas_guardadas}, ensure_ascii=False),
        height=70,
        key="editor_json_input",
        label_visibility="collapsed",
    )
    col_a, col_b, col_c = app.st.columns([1, 1, 4])
    with col_a:
        if app.st.button("Guardar", type="primary", key="btn_guardar_editor"):
            try:
                data = json.loads(json_input)
                guardar_posiciones_equipos(data.get("equipos", {}))
                guardar_zonas(data.get("zonas", []))
                app.st.success("Equipos y zonas guardados correctamente.")
                app.st.rerun()
            except Exception as exc:
                app.st.error(f"JSON inválido: {exc}")
    with col_b:
        if app.st.button("Limpiar todo", key="btn_limpiar_editor"):
            guardar_posiciones_equipos({})
            guardar_zonas([])
            app.st.rerun()

    editor_fs = _generar_editor_fullscreen_html(
        orto_preview_bytes, equipos_activos, posiciones_equipos
    )
    app.st.download_button(
        "Abrir editor en pantalla completa",
        data=editor_fs.encode("utf-8"),
        file_name="editor_mina.html",
        mime="text/html",
        key="btn_fs_editor",
    )

    # ── Descarga con equipos marcados (Pillow) ──────────────────────────
    if posiciones_equipos:
        app.st.divider()
        app.st.subheader("Descarga con equipos marcados")
        app.st.caption(f"{len(posiciones_equipos)} equipo(s) posicionado(s) en el mapa.")
        if app.st.button("Generar imagen con equipos"):
            with app.st.spinner("Componiendo imagen..."):
                try:
                    buf = generar_imagen_con_equipos(
                        ortomosaico.ruta_preview, posiciones_equipos, equipos_activos
                    )
                    app.st.download_button(
                        label="Descargar JPG",
                        data=buf,
                        file_name="ortomosaico_equipos.jpg",
                        mime="image/jpeg",
                    )
                except Exception as exc:
                    app.st.error(f"Error al generar imagen: {exc}")

    with app.st.expander("Detalle del archivo"):
        app.st.write(f"Fuente maestra: `{ortomosaico.ruta_maestra}`")
        app.st.write(f"Vista previa: `{ortomosaico.ruta_preview}`")
        app.st.write(f"Posiciones guardadas en: `{POSICIONES_PATH}`")
        app.st.write(f"Zonas guardadas en: `{ZONAS_PATH}`")


main()
