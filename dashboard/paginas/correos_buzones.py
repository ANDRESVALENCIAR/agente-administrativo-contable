"""Correos: bandeja unificada de los buzones conectados, gestión de buzones y niveles de alerta."""
from __future__ import annotations

from html import escape

import streamlit as st

from modulos import buzones as bz

NIV_COL = {"CRITICO": "#E5484D", "URGENTE": "#FF6A3D", "AVISO": "#F5C542", "INFO": "#7DD3FC", "NO": "#52525B"}
NIV_TXT = {"CRITICO": "Crítica", "URGENTE": "Urgente", "AVISO": "Aviso", "INFO": "Solo registrar", "NO": "No alertar"}

CSS = """
<style>
.bz-hero{border:1px solid #1F2024;border-radius:22px;padding:20px 22px;margin-bottom:12px;
 background:radial-gradient(120% 160% at 100% 0%,#0E1620 0%,#0A0B0D 60%)}
.bz-eb{font-family:'Geist Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8B8B93;text-transform:uppercase}
.bz-boxes{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin-top:12px}
.bz-box{background:#0F1012;border:1px solid #1F2024;border-radius:14px;padding:12px 14px}
.bz-box b{color:#fff;font-size:14px;font-weight:500;word-break:break-all}
.bz-box span{display:block;font-family:'Geist Mono',monospace;font-size:10.5px;margin-top:5px;color:#8B8B93}
.bz-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px}
.bz-row{display:flex;gap:12px;padding:11px 4px;border-top:1px solid #17181C}
.bz-bar{width:4px;border-radius:4px;flex:0 0 4px}
.bz-t{color:#fff;font-size:14.5px;font-weight:500;line-height:1.3}
.bz-s{color:#8B8B93;font-size:12px;margin-top:3px}.bz-r{color:#A1A1AA;font-size:12.5px;margin-top:4px;line-height:1.45}
.bz-tag{font-family:'Geist Mono',monospace;font-size:9.5px;letter-spacing:.06em;padding:2px 7px;border-radius:6px;
 margin-right:8px;vertical-align:1px}
</style>
"""


def _estado_html(b: dict) -> str:
    if not b["activo"]:
        return '<span><i class="bz-dot" style="background:#52525B"></i>Pausado</span>'
    if not b["tiene_clave"]:
        return '<span><i class="bz-dot" style="background:#F5C542"></i>Falta contraseña</span>'
    if b["estado"] == "ERROR":
        return '<span><i class="bz-dot" style="background:#E5484D"></i>Error al leer</span>'
    if b["estado"] == "OK":
        return (f'<span><i class="bz-dot" style="background:#4ADE80"></i>Conectado · leído '
                f'{escape(str(b["ultima_lectura"] or "")[:16])}</span>')
    return '<span><i class="bz-dot" style="background:#8B8B93"></i>Sin probar</span>'


def _hero() -> None:
    r = bz.resumen()
    cajas = "".join(f'<div class="bz-box"><b>{escape(b["email"])}</b>{_estado_html(b)}</div>' for b in r["buzones"])
    st.markdown(f'<div class="bz-hero"><div class="bz-eb">Buzones conectados · solo lectura</div>'
                f'<div style="color:#fff;font-size:22px;font-weight:600;margin-top:4px">'
                f'{r["importantes"]} correo(s) importante(s) sin atender</div>'
                f'<div class="bz-boxes">{cajas}</div></div>', unsafe_allow_html=True)


def render_bandeja() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _hero()
    nv = bz.niveles()
    c1, c2, c3, c4 = st.columns([1.2, 1.4, 1, 1])
    buz = {b["email"]: b["id"] for b in bz.listar_buzones()}
    sel_b = c1.selectbox("Buzón", ["Todos"] + list(buz), key="bz_buz")
    cats = ["Importantes", "Todas"] + list(bz.CATEGORIAS)
    sel_c = c2.selectbox("Categoría", cats, key="bz_cat",
                         format_func=lambda k: bz.CATEGORIAS[k]["nombre"] if k in bz.CATEGORIAS else k)
    sel_e = c3.selectbox("Estado", ["NUEVO", "ATENDIDO", "ARCHIVADO", "Todos"], key="bz_est",
                         format_func=lambda e: {"NUEVO": "Sin atender", "ATENDIDO": "Atendidos",
                                                "ARCHIVADO": "Archivados", "Todos": "Todos"}[e])
    if c4.button("Leer correos ahora", type="primary", width="stretch"):
        with st.spinner("Leyendo buzones…"):
            r = bz.leer_todos()
        errores = [x for x in r["buzones"] if x.get("error")]
        st.toast(f"{r['nuevos']} correo(s) nuevo(s)" + (f" · {len(errores)} buzón(es) con problema" if errores else ""))
        st.rerun()
    filas = bz.bandeja(estado=None if sel_e == "Todos" else sel_e,
                       categoria=sel_c if sel_c in bz.CATEGORIAS else None,
                       buzon_id=buz.get(sel_b))
    if sel_c == "Importantes":
        filas = [f for f in filas if nv.get(f["categoria"]) in ("CRITICO", "URGENTE", "AVISO")]
    if not filas:
        st.info("No hay correos con este filtro. Conecte los buzones en la pestaña «Buzones conectados».")
        return
    orden = {"CRITICO": 0, "URGENTE": 1, "AVISO": 2, "INFO": 3, "NO": 4}
    filas.sort(key=lambda f: str(f["fecha"]), reverse=True)
    filas.sort(key=lambda f: orden.get(nv.get(f["categoria"], "NO"), 9))
    for f in filas[:150]:
        nivel = nv.get(f["categoria"], "NO")
        col = NIV_COL[nivel]
        cat = bz.CATEGORIAS.get(f["categoria"], {}).get("nombre", f["categoria"])
        extra = ""
        if f["datos"].get("emisor"):
            extra = f' · Emisor {escape(f["datos"]["emisor"])} (NIT {escape(f["datos"]["nit"])}) · N.º {escape(f["datos"]["numero"])}'
        adj = f' · 📎 {escape(", ".join(f["adjuntos"][:3]))}' if f["adjuntos"] else ""
        st.markdown(
            f'<div class="bz-row"><div class="bz-bar" style="background:{col}"></div><div style="flex:1">'
            f'<div class="bz-t"><span class="bz-tag" style="color:{col};border:1px solid {col}66">{escape(cat.upper())}</span>'
            f'{escape(f["asunto"] or "(sin asunto)")}</div>'
            f'<div class="bz-s">De {escape(f["remitente_nombre"] or f["remitente"])} &lt;{escape(f["remitente"])}&gt; → '
            f'{escape(f["buzon"])} · {escape(str(f["fecha"])[:16])}{extra}{adj}</div>'
            f'<div class="bz-r">{escape((f["resumen"] or "")[:260])}</div></div></div>',
            unsafe_allow_html=True)
        if f["estado"] == "NUEVO":
            a, b, c = st.columns([1, 1, 2])
            if a.button("Atendido ✓", key=f"bz_at_{f['id']}", width="stretch"):
                bz.marcar(f["id"], "ATENDIDO")
                st.rerun()
            if b.button("Archivar", key=f"bz_ar_{f['id']}", width="stretch"):
                bz.marcar(f["id"], "ARCHIVADO")
                st.rerun()
            nueva = c.selectbox("Corregir categoría", list(bz.CATEGORIAS), key=f"bz_rc_{f['id']}",
                                index=list(bz.CATEGORIAS).index(f["categoria"]) if f["categoria"] in bz.CATEGORIAS else 0,
                                format_func=lambda k: bz.CATEGORIAS[k]["nombre"], label_visibility="collapsed")
            if nueva != f["categoria"]:
                bz.reclasificar(f["id"], nueva)
                st.rerun()


def render_buzones() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("Shaki lee estos buzones **cada 10 minutos en modo solo lectura**: no marca como leído, no mueve "
                "ni borra nada. Las contraseñas quedan solo en este computador (archivo `.env`).")
    for b in bz.listar_buzones():
        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            c1.markdown(f"**{b['email']}**  \nServidor `{b['imap_host']}:{b['imap_port']}`")
            c1.markdown(_estado_html(b).replace("<span>", "").replace("</span>", ""), unsafe_allow_html=True)
            if b.get("ultimo_error"):
                c1.caption(b["ultimo_error"])
            if not b["tiene_clave"]:
                c1.code(f'powershell -ExecutionPolicy Bypass -File scripts\\configurar_buzon.ps1 -Correo {b["email"]}',
                        language="powershell")
            x1, x2, x3 = c2.columns(3)
            if x1.button("Probar", key=f"bzp_{b['id']}", width="stretch"):
                r = bz.probar(b["id"])
                (st.success if r["ok"] else st.error)(
                    f"Conectado: {r.get('mensajes')} correos en la bandeja" if r["ok"] else r["error"])
            if x2.button("Pausar" if b["activo"] else "Activar", key=f"bza_{b['id']}", width="stretch"):
                bz.actualizar_buzon(b["id"], activo=0 if b["activo"] else 1)
                st.rerun()
            with x3.popover("Ajustes", width="stretch"):
                host = st.text_input("Servidor IMAP", b["imap_host"], key=f"bzh_{b['id']}")
                puerto = st.number_input("Puerto", value=int(b["imap_port"] or 993), key=f"bzpt_{b['id']}")
                usuario = st.text_input("Usuario", b["usuario"] or b["email"], key=f"bzu_{b['id']}")
                ssl_ok = st.toggle("Verificar certificado SSL", value=bool(b["verificar_ssl"]), key=f"bzs_{b['id']}")
                if st.button("Guardar", key=f"bzg_{b['id']}"):
                    bz.actualizar_buzon(b["id"], imap_host=host.strip(), imap_port=int(puerto),
                                        usuario=usuario.strip(), verificar_ssl=int(ssl_ok))
                    st.rerun()
    st.markdown("#### Conectar otro buzón")
    with st.form("bz_nuevo"):
        correo = st.text_input("Correo", placeholder="facturacion@viaindustrial.com")
        if st.form_submit_button("Agregar"):
            try:
                bz.agregar_buzon(correo)
                st.success("Agregado. Ahora ejecute en el computador de Shaki el comando que aparece en el buzón "
                           "para guardar su contraseña.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    st.caption("Gmail: active la verificación en 2 pasos y cree una contraseña de aplicación en "
               "myaccount.google.com/apppasswords. Correos @viaindustrial.com: la misma contraseña con la que entra "
               "al webmail; el servidor es mail.viaindustrial.com.")


def render_niveles() -> None:
    st.markdown("Elija **qué tan fuerte avisa Shaki** por cada tipo de correo. Crítica = correo inmediato a dirección y "
                "gerencia; Urgente y Aviso = Centro de alertas y resumen diario; Solo registrar = queda en la bandeja; "
                "No alertar = se archiva solo.")
    actual = bz.niveles()
    nuevo = {}
    for k, v in bz.CATEGORIAS.items():
        c1, c2 = st.columns([2.2, 1.3])
        c1.markdown(f"**{v['nombre']}**  \n<span style='color:#8B8B93;font-size:12.5px'>{escape(v['desc'])}</span>",
                    unsafe_allow_html=True)
        nuevo[k] = c2.selectbox(v["nombre"], bz.NIVELES_ALERTA, index=bz.NIVELES_ALERTA.index(actual[k]),
                                format_func=lambda n: NIV_TXT[n], key=f"bzn_{k}", label_visibility="collapsed")
    if nuevo != actual:
        bz.guardar_niveles(nuevo)
        try:
            from modulos import motor_alertas
            motor_alertas.escanear(notificar=False)
        except Exception:
            pass
        st.toast("Niveles guardados")
