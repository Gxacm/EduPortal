from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timedelta
from sqlalchemy import inspect, text
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from sqlalchemy.orm import joinedload
import os
from werkzeug.utils import secure_filename
from models import db, Usuarios, Maestros, CiclosLectivos, Periodos, Alumnos, Clases, Notas, Asistencias, Horarios, Anuncios, Grados, Secciones, Horarios, Tareas, EntregasTareas, Examenes, PreguntasExamen, OpcionesPregunta, EntregasExamenes, DocumentosClase, EnlacesClase, VideosClase, ForosClase, MensajesForoClase


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def asegurar_columnas_panel_maestro():
    inspector = inspect(db.engine)

    columnas_tareas = {col['name'] for col in inspector.get_columns('tareas')}
    columnas_examenes = {col['name'] for col in inspector.get_columns('examenes')}
    columnas_entregas_tareas = {col['name'] for col in inspector.get_columns('entregas_tareas')}

    with db.engine.begin() as conn:
        if 'periodo' not in columnas_tareas:
            conn.execute(text("ALTER TABLE tareas ADD COLUMN IF NOT EXISTS periodo VARCHAR(50)"))
        if 'puntos' not in columnas_tareas:
            conn.execute(text("ALTER TABLE tareas ADD COLUMN IF NOT EXISTS puntos DOUBLE PRECISION DEFAULT 100"))
        if 'archivo_adjunto_ruta' not in columnas_tareas:
            conn.execute(text("ALTER TABLE tareas ADD COLUMN IF NOT EXISTS archivo_adjunto_ruta VARCHAR(255)"))
        if 'archivo_adjunto_nombre' not in columnas_tareas:
            conn.execute(text("ALTER TABLE tareas ADD COLUMN IF NOT EXISTS archivo_adjunto_nombre VARCHAR(255)"))
        if 'periodo' not in columnas_examenes:
            conn.execute(text("ALTER TABLE examenes ADD COLUMN IF NOT EXISTS periodo VARCHAR(50)"))
        if 'archivo_nombre' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS archivo_nombre VARCHAR(255)"))
        if 'comentario_alumno' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS comentario_alumno TEXT"))
        if 'comentario_maestro' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS comentario_maestro TEXT"))
        if 'archivo_revision_ruta' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS archivo_revision_ruta VARCHAR(255)"))
        if 'archivo_revision_nombre' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS archivo_revision_nombre VARCHAR(255)"))
        if 'fecha_entrega' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS fecha_entrega TIMESTAMP"))
        if 'fecha_revision' not in columnas_entregas_tareas:
            conn.execute(text("ALTER TABLE entregas_tareas ADD COLUMN IF NOT EXISTS fecha_revision TIMESTAMP"))


with app.app_context():
    db.create_all()
    asegurar_columnas_panel_maestro()

# ==============================================================================
# ----------------------------- Configuracion Idioma ---------------------------
# ==============================================================================
import locale
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.utf8') 
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except locale.Error:
        print("No se pudo establecer el locale en español, se usará el predeterminado.")

def fecha_en_espanol(fecha):
    if not fecha:
        return ""
    
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    
    dia = fecha.day
    mes = meses[fecha.month]
    año = fecha.year
    
    return f"{dia} de {mes}, {año}"
app.jinja_env.filters['fecha_es'] = fecha_en_espanol

def normalizar_url_externa(url):
    if not url:
        return ''
    url = url.strip()
    if url and not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url

def obtener_video_embed_url(url):
    url = normalizar_url_externa(url)
    if 'youtube.com/watch?v=' in url:
        video_id = url.split('watch?v=')[1].split('&')[0]
        return f'https://www.youtube.com/embed/{video_id}'
    if 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[1].split('?')[0]
        return f'https://www.youtube.com/embed/{video_id}'
    if 'youtube.com/embed/' in url:
        return url
    return None

def guardar_archivo_subido(file_storage, carpeta_relativa, prefijo='archivo'):
    if not file_storage or file_storage.filename == '':
        return None, None
    filename = secure_filename(file_storage.filename)
    nombre_final = f"{prefijo}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    carpeta_absoluta = os.path.join(app.root_path, 'static', 'uploads', carpeta_relativa)
    os.makedirs(carpeta_absoluta, exist_ok=True)
    ruta_absoluta = os.path.join(carpeta_absoluta, nombre_final)
    file_storage.save(ruta_absoluta)
    return os.path.join('static', 'uploads', carpeta_relativa, nombre_final), filename

def alumno_tiene_acceso_clase(alumno, clase):
    return bool(alumno and alumno.seccion and clase and clase.id_grado == alumno.seccion.id_grado)

def maestro_posee_clase(perfil_maestro, id_clase, id_grado=None):
    if not perfil_maestro or not id_clase:
        return None
    filtros = [Clases.id_clase == int(id_clase), Clases.id_maestro == perfil_maestro.id_maestro]
    if id_grado is not None:
        filtros.append(Clases.id_grado == id_grado)
    return Clases.query.filter(*filtros).first()

def construir_resumen_aula(clase_obj, alumno=None):
    documentos = DocumentosClase.query.filter_by(id_clase=clase_obj.id_clase).order_by(DocumentosClase.fecha_publicacion.desc()).all()
    enlaces = EnlacesClase.query.filter_by(id_clase=clase_obj.id_clase).order_by(EnlacesClase.fecha_publicacion.desc()).all()
    videos = VideosClase.query.filter_by(id_clase=clase_obj.id_clase).order_by(VideosClase.fecha_publicacion.desc()).all()
    foros = ForosClase.query.filter_by(id_clase=clase_obj.id_clase).order_by(ForosClase.fecha_publicacion.desc()).all()
    examenes = Examenes.query.filter_by(id_clase=clase_obj.id_clase).order_by(Examenes.fecha_limite.asc()).all()

    entregadas_ids = []
    examenes_entregados_ids = []
    if alumno:
        entregadas_ids = [e.id_tarea for e in EntregasTareas.query.filter_by(id_alumno=alumno.id_alumno).all()]
        examenes_entregados_ids = [e.id_examen for e in EntregasExamenes.query.filter_by(id_alumno=alumno.id_alumno).all()]

    return {
        'documentos': documentos,
        'enlaces': enlaces,
        'videos': videos,
        'foros': foros,
        'examenes': examenes,
        'entregadas_ids': entregadas_ids,
        'examenes_entregados_ids': examenes_entregados_ids
    }

DIA_ORDEN = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes']
DIA_LABELS = {
    'Lunes': 'Lunes',
    'Martes': 'Martes',
    'Miercoles': 'Miércoles',
    'Jueves': 'Jueves',
    'Viernes': 'Viernes'
}
ESTADOS_ASISTENCIA_UI = {
    'Presente': {
        'clase': 'estado-presente',
        'texto': 'Asististe',
        'color': '#16a34a',
        'fondo': '#dcfce7',
        'borde': '#86efac',
        'icono': 'bi-check-circle-fill'
    },
    'Ausente': {
        'clase': 'estado-ausente',
        'texto': 'Inasistencia',
        'color': '#dc2626',
        'fondo': '#fee2e2',
        'borde': '#fca5a5',
        'icono': 'bi-x-circle-fill'
    },
    'Excusa': {
        'clase': 'estado-excusa',
        'texto': 'Excusa registrada',
        'color': '#ca8a04',
        'fondo': '#fef3c7',
        'borde': '#fcd34d',
        'icono': 'bi-exclamation-circle-fill'
    },
    'Feriado': {
        'clase': 'estado-feriado',
        'texto': 'Feriado',
        'color': '#2563eb',
        'fondo': '#dbeafe',
        'borde': '#93c5fd',
        'icono': 'bi-calendar2-x-fill'
    },
    'Sin registro': {
        'clase': 'estado-sin-registro',
        'texto': 'Sin registro',
        'color': '#64748b',
        'fondo': '#f8fafc',
        'borde': '#e2e8f0',
        'icono': 'bi-dash-circle-fill'
    }
}


def ordenar_dia_semana(dia):
    try:
        return DIA_ORDEN.index(dia)
    except ValueError:
        return len(DIA_ORDEN)


def describir_rango_hora(hora_inicio, hora_fin):
    return f"{hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}"


def obtener_semana_actual():
    hoy = datetime.now().date()
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes, [lunes + timedelta(days=offset) for offset in range(5)]


def obtener_slots_candidatos_desde_origen(horarios_origen):
    slots = []
    vistos = set()

    for bloque in sorted(
        horarios_origen,
        key=lambda item: (ordenar_dia_semana(item.dia_semana), item.hora_inicio, item.hora_fin)
    ):
        firma = (bloque.dia_semana, bloque.hora_inicio, bloque.hora_fin)
        if firma not in vistos:
            vistos.add(firma)
            slots.append({
                'dia': bloque.dia_semana,
                'inicio': bloque.hora_inicio,
                'fin': bloque.hora_fin
            })

    return slots


def existe_solapamiento(hora_inicio, hora_fin, otro_inicio, otro_fin):
    return hora_inicio < otro_fin and hora_fin > otro_inicio


def validar_bloque_horario(id_clase, id_seccion, dia_semana, hora_inicio, hora_fin, excluir_id=None):
    seccion = Secciones.query.get(id_seccion)
    clase = Clases.query.get(id_clase)

    if not seccion or not clase:
        return "La sección o la materia seleccionada no existen."

    if seccion.id_grado != clase.id_grado:
        return "La materia debe pertenecer al mismo grado de la sección seleccionada."

    conflicto_seccion = Horarios.query.filter(
        Horarios.id_seccion == id_seccion,
        Horarios.dia_semana == dia_semana,
        Horarios.hora_inicio < hora_fin,
        Horarios.hora_fin > hora_inicio
    )

    if excluir_id:
        conflicto_seccion = conflicto_seccion.filter(Horarios.id_horario != excluir_id)

    if conflicto_seccion.first():
        return "Ya existe otra clase ocupando ese bloque en la sección seleccionada."

    if clase.id_maestro:
        conflicto_maestro = db.session.query(Horarios).join(Clases).filter(
            Clases.id_maestro == clase.id_maestro,
            Horarios.dia_semana == dia_semana,
            Horarios.hora_inicio < hora_fin,
            Horarios.hora_fin > hora_inicio
        )

        if excluir_id:
            conflicto_maestro = conflicto_maestro.filter(Horarios.id_horario != excluir_id)

        if conflicto_maestro.first():
            return "El maestro asignado ya tiene otra clase en ese mismo horario."

    return None


def generar_propuesta_horario_para_seccion(seccion_destino, horarios_origen, slots_candidatos):
    propuesta = []
    slots_usados = set()

    bloques_ordenados = sorted(
        horarios_origen,
        key=lambda item: (
            item.clase.id_maestro or 0,
            ordenar_dia_semana(item.dia_semana),
            item.hora_inicio,
            item.id_horario
        )
    )

    for bloque in bloques_ordenados:
        clase = bloque.clase
        slot_asignado = None

        for slot in slots_candidatos:
            firma_slot = (slot['dia'], slot['inicio'], slot['fin'])
            if firma_slot in slots_usados:
                continue

            conflicto_local = any(
                item['dia_semana'] == slot['dia'] and
                existe_solapamiento(item['hora_inicio'], item['hora_fin'], slot['inicio'], slot['fin'])
                for item in propuesta
            )
            if conflicto_local:
                continue

            if clase.id_maestro:
                conflicto_maestro = db.session.query(Horarios).join(Clases).filter(
                    Clases.id_maestro == clase.id_maestro,
                    Horarios.id_seccion != seccion_destino.id_seccion,
                    Horarios.dia_semana == slot['dia'],
                    Horarios.hora_inicio < slot['fin'],
                    Horarios.hora_fin > slot['inicio']
                ).first()
                if conflicto_maestro:
                    continue

            slot_asignado = slot
            break

        if not slot_asignado:
            return None

        slots_usados.add((slot_asignado['dia'], slot_asignado['inicio'], slot_asignado['fin']))
        propuesta.append({
            'id_clase': bloque.id_clase,
            'dia_semana': slot_asignado['dia'],
            'hora_inicio': slot_asignado['inicio'],
            'hora_fin': slot_asignado['fin']
        })

    return propuesta


def sincronizar_horarios_grado_desde_seccion(id_seccion_origen):
    seccion_origen = Secciones.query.get(id_seccion_origen)
    if not seccion_origen:
        return {'ok': False, 'mensaje': 'No se encontró la sección base seleccionada.'}

    horarios_origen = Horarios.query.options(joinedload(Horarios.clase)).filter_by(
        id_seccion=id_seccion_origen
    ).all()
    if not horarios_origen:
        return {'ok': False, 'mensaje': 'La sección base aún no tiene bloques de horario registrados.'}

    slots_candidatos = obtener_slots_candidatos_desde_origen(horarios_origen)
    secciones_destino = Secciones.query.filter(
        Secciones.id_grado == seccion_origen.id_grado,
        Secciones.id_seccion != seccion_origen.id_seccion
    ).order_by(Secciones.nombre_seccion.asc()).all()

    if not secciones_destino:
        return {'ok': True, 'sincronizadas': [], 'omitidas': []}

    sincronizadas = []
    omitidas = []

    for seccion_destino in secciones_destino:
        propuesta = generar_propuesta_horario_para_seccion(seccion_destino, horarios_origen, slots_candidatos)

        if not propuesta:
            omitidas.append(seccion_destino.nombre_seccion)
            continue

        Horarios.query.filter_by(id_seccion=seccion_destino.id_seccion).delete(synchronize_session=False)

        for bloque in propuesta:
            db.session.add(Horarios(
                id_clase=bloque['id_clase'],
                id_seccion=seccion_destino.id_seccion,
                dia_semana=bloque['dia_semana'],
                hora_inicio=bloque['hora_inicio'],
                hora_fin=bloque['hora_fin']
            ))

        sincronizadas.append(seccion_destino.nombre_seccion)

    return {
        'ok': True,
        'sincronizadas': sincronizadas,
        'omitidas': omitidas
    }


def construir_matriz_horario_alumno(alumno):
    if not alumno or not alumno.seccion:
        return {
            'filas': [],
            'dias': [],
            'semana_label': '',
            'semana_corta': ''
        }

    lunes, dias_semana = obtener_semana_actual()
    bloques = Horarios.query.options(
        joinedload(Horarios.clase).joinedload(Clases.maestro_titular).joinedload(Maestros.usuario)
    ).filter_by(id_seccion=alumno.id_seccion).all()

    dias = []
    for fecha in dias_semana:
        dia_db = DIA_ORDEN[fecha.weekday()]
        dias.append({
            'db': dia_db,
            'label': DIA_LABELS[dia_db],
            'fecha': fecha.strftime('%d/%m')
        })

    if not bloques:
        semana_label = f"Semana del {lunes.strftime('%d/%m')} al {(lunes + timedelta(days=4)).strftime('%d/%m')}"
        return {
            'filas': [],
            'dias': dias,
            'semana_label': semana_label,
            'semana_corta': lunes.strftime('%Y')
        }

    clases_ids = sorted({bloque.id_clase for bloque in bloques})
    asistencias = Asistencias.query.filter(
        Asistencias.id_alumno == alumno.id_alumno,
        Asistencias.id_clase.in_(clases_ids),
        Asistencias.fecha >= lunes,
        Asistencias.fecha <= lunes + timedelta(days=4)
    ).all()
    asistencias_map = {(asistencia.id_clase, asistencia.fecha): asistencia.estado for asistencia in asistencias}

    colores_base = ['#4361ee', '#2ecc71', '#ff9f43', '#9b59b6', '#e74c3c', '#0ea5e9', '#14b8a6']
    color_por_clase = {}
    filas_indexadas = {}

    for indice, bloque in enumerate(sorted(
        bloques,
        key=lambda item: (item.hora_inicio, item.hora_fin, ordenar_dia_semana(item.dia_semana))
    )):
        clave = (bloque.hora_inicio, bloque.hora_fin)
        if clave not in filas_indexadas:
            filas_indexadas[clave] = {
                'hora': describir_rango_hora(bloque.hora_inicio, bloque.hora_fin),
                'tipo': 'clase',
                'celdas': {dia['db']: None for dia in dias}
            }

        if bloque.id_clase not in color_por_clase:
            color_por_clase[bloque.id_clase] = colores_base[indice % len(colores_base)]

        fecha_bloque = lunes + timedelta(days=ordenar_dia_semana(bloque.dia_semana))
        estado = asistencias_map.get((bloque.id_clase, fecha_bloque), 'Sin registro')
        estado_ui = ESTADOS_ASISTENCIA_UI.get(estado, ESTADOS_ASISTENCIA_UI['Sin registro']).copy()

        maestro = None
        if bloque.clase and bloque.clase.maestro_titular and bloque.clase.maestro_titular.usuario:
            maestro = f"{bloque.clase.maestro_titular.usuario.nombre} {bloque.clase.maestro_titular.usuario.apellido}"

        filas_indexadas[clave]['celdas'][bloque.dia_semana] = {
            'materia': bloque.clase.nombre_clase if bloque.clase else 'Clase',
            'maestro': maestro,
            'accent': color_por_clase[bloque.id_clase],
            'estado': estado,
            'estado_ui': estado_ui,
            'horario': describir_rango_hora(bloque.hora_inicio, bloque.hora_fin)
        }

    filas = [filas_indexadas[clave] for clave in sorted(filas_indexadas.keys())]
    semana_label = f"Semana del {lunes.strftime('%d/%m')} al {(lunes + timedelta(days=4)).strftime('%d/%m')}"

    return {
        'filas': filas,
        'dias': dias,
        'semana_label': semana_label,
        'semana_corta': lunes.strftime('%Y')
    }

@app.context_processor
def inject_ciclo_activo():
    ciclo_activo = CiclosLectivos.query.filter_by(estado='ACTIVO').first()
    
    if ciclo_activo:
        return dict(ciclo_actual_global=ciclo_activo.nombre_ciclo)
        
    return dict(ciclo_actual_global="Sin Ciclo Activo")

# ==============================================================================
# ----------------------------- RUTA RAÍZ Y LOGIN ------------------------------
# ==============================================================================
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        user = Usuarios.query.filter_by(correo=correo).first()
        
        if user and check_password_hash(user.contrasena, password):
            session['user_id'] = user.id_usuario
            session['rol'] = user.id_rol
            session['nombre'] = f"{user.nombre} {user.apellido}"
            session['iniciales'] = f"{user.nombre[0]}{user.apellido[0]}".upper()
            
            if user.id_rol == 1: 
                session['rol_nombre'] = "Administrador"
                return redirect(url_for('admin_dashboard'))
            elif user.id_rol == 2: 
                session['rol_nombre'] = "Maestro"
                return redirect(url_for('maestro_dashboard'))
            elif user.id_rol == 3:
                session['rol_nombre'] = "Alumno"
                return redirect(url_for('alumno_dashboard'))
                
        flash("Credenciales incorrectas.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==============================================================================
# --------------------------- CONFIGURACIÓN Y AJUSTES --------------------------
# ==============================================================================

@app.route('/mi-cuenta')
def mi_cuenta():
    # 1. Verificación de sesión
    if not session.get('user_id'): 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    usuario = Usuarios.query.get(user_id)

    if usuario.id_rol == 1:
        return redirect(url_for('admin_dashboard'))

    if usuario.id_rol == 2:
        perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    elif usuario.id_rol == 3:
        perfil = Alumnos.query.filter_by(id_usuario=user_id).first()
    else:
        perfil = None 

    return render_template('mi_cuenta.html', usuario=usuario, perfil=perfil)



@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    if not session.get('user_id'): 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    rol = session.get('rol')
    # Usamos .get() para asegurar que el objeto esté vinculado a la sesión actual
    usuario = Usuarios.query.get(user_id)

    if request.method == 'POST':
        accion = request.form.get('accion')

        # --- CAMBIO DE CONTRASEÑA (CORREGIDO) ---
        if accion == 'cambiar_pass':
            pass_actual = request.form.get('pass_actual')
            pass_nueva = request.form.get('pass_nueva')
            confirm_pass = request.form.get('confirm_pass')

            if not check_password_hash(usuario.contrasena, pass_actual):
                flash("La contraseña actual no es correcta.", "error")
            elif pass_nueva != confirm_pass:
                flash("Las contraseñas nuevas no coinciden.", "error")
            elif len(pass_nueva) < 8:
                flash("La contraseña debe tener al menos 8 caracteres.", "error")
            else:
                try:
                    usuario.contrasena = generate_password_hash(pass_nueva)
                    flag_modified(usuario, "contrasena")
                    db.session.add(usuario) # Re-vincular objeto
                    db.session.commit()
                    flash("¡Contraseña actualizada con éxito!", "success")
                except Exception as e:
                    db.session.rollback()
                    flash("Error al actualizar la base de datos.", "error")

        # --- NOTIFICACIONES Y OTROS ---
        elif accion == 'actualizar_notificaciones':
            # Aquí procesarías los checkboxes si decides guardarlos en DB
            flash("Preferencias de notificación actualizadas.", "success")

        return redirect(url_for('ajustes'))

    return render_template('ajustes.html', usuario=usuario, rol=rol)

# ==============================================================================
# ------------------------------ PANEL DEL MAESTRO -----------------------------
# ==============================================================================

@app.route('/maestro')
def maestro_dashboard():
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    maestro_usuario = Usuarios.query.get(user_id) 
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro).all() if perfil else []
    ids_grados_maestro = list({clase.id_grado for clase in clases})
    anuncios = Anuncios.query.filter(
        (Anuncios.dirigido_a.in_(['Todos', 'Maestros'])) |
        (Anuncios.dirigido_a.in_([f'Grado_{id_grado}' for id_grado in ids_grados_maestro]))
    ).order_by(Anuncios.fecha_publicacion.desc()).limit(5).all()
    
    grados_data = []
    ids_grados_vistos = set()
    for c in clases:
        if c.id_grado not in ids_grados_vistos:
            grado = Grados.query.get(c.id_grado)
            grados_data.append({'grado': grado, 'clases': [c]})
            ids_grados_vistos.add(c.id_grado)
            
    return render_template('Panel_Maestro/maestro_dash.html', 
                           maestro=maestro_usuario, clases=clases, 
                           total_clases=len(clases), grados_data=grados_data, anuncios=anuncios)

# --- GESTIÓN DE TAREAS CORREGIDA ---

@app.route('/maestro/tareas/historial/<int:id_grado>')
def historial_tareas(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    grado = Grados.query.get_or_404(id_grado)
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []
    clases_grado = Clases.query.filter_by(id_grado=id_grado).all()
    ids_clases = [c.id_clase for c in clases_grado]
    
    tareas = Tareas.query.filter(Tareas.id_clase.in_(ids_clases)).order_by(Tareas.fecha_entrega.desc()).all()
        
    return render_template('Panel_Maestro/tareas_historial.html', tareas=tareas, id_grado=id_grado, grado=grado)

@app.route('/maestro/tareas/crear/<int:id_grado>')
def vista_nueva_tarea(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    grado = Grados.query.get_or_404(id_grado)
    
    # Solo mostramos las materias de este maestro en este grado específico
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []
    
    return render_template(
        'Panel_Maestro/tareas_nuevas.html',
        clases=clases,
        id_grado=id_grado,
        grado=grado,
        periodos=obtener_periodos_disponibles()
    )

@app.route('/maestro/tareas/nueva/<int:id_grado>', methods=['POST'])
def crear_tarea(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    try:
        puntos = float(request.form.get('puntos', 100))
        if puntos <= 0:
            raise ValueError("Puntaje invalido")

        archivo_adjunto_ruta = None
        archivo_adjunto_nombre = None
        archivo_tarea = request.files.get('archivo_tarea')
        if archivo_tarea and archivo_tarea.filename:
            archivo_adjunto_ruta, archivo_adjunto_nombre = guardar_archivo_subido(
                archivo_tarea,
                'tareas_material',
                f'tarea_docente_{request.form.get("id_clase") or "clase"}'
            )

        nueva_tarea = Tareas(
            id_clase=request.form.get('id_clase'),
            titulo=request.form.get('titulo'),
            descripcion=request.form.get('descripcion'),
            periodo=request.form.get('periodo'),
            puntos=puntos,
            archivo_adjunto_ruta=archivo_adjunto_ruta,
            archivo_adjunto_nombre=archivo_adjunto_nombre,
            fecha_entrega=datetime.strptime(request.form.get('fecha_entrega'), '%Y-%m-%dT%H:%M')
        )
        db.session.add(nueva_tarea)
        db.session.commit()
        flash("Tarea creada exitosamente", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear tarea: {e}") 
        flash("Error al crear tarea. Revisa los datos.", "danger")

    return redirect(url_for('gestionar_grado', id_grado=id_grado))

# --- REVISIÓN DE ASIGNACIONES (NOTAS) ACTUALIZADA ---

@app.route('/maestro/notas/general/<int:id_grado>', methods=['GET', 'POST'])
def registrar_notas(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    grado = Grados.query.get_or_404(id_grado)

    # 1. LÓGICA PARA GUARDAR LAS NOTAS (MÉTODO POST)
    if request.method == 'POST':
        id_tarea = request.args.get('id_tarea')
        
        if id_tarea:
            tarea_obj = Tareas.query.join(Clases, Clases.id_clase == Tareas.id_clase).filter(
                Tareas.id_tarea == id_tarea,
                Clases.id_maestro == perfil.id_maestro
            ).first()

            if not tarea_obj:
                flash("La tarea seleccionada no pertenece a este maestro.", "danger")
                return redirect(url_for('registrar_notas', id_grado=id_grado))

            puntaje_maximo = float(tarea_obj.puntos or 0)

            for key, value in request.form.items():
                if not key.startswith('nota_'):
                    continue

                id_alumno = int(key.split('_')[1])
                entrega_registro = EntregasTareas.query.filter_by(id_alumno=id_alumno, id_tarea=id_tarea).first()

                comentario_maestro = (request.form.get(f'comentario_{id_alumno}') or '').strip()
                archivo_revision = request.files.get(f'archivo_revision_{id_alumno}')

                if entrega_registro:
                    if comentario_maestro:
                        entrega_registro.comentario_maestro = comentario_maestro
                        entrega_registro.fecha_revision = datetime.utcnow()
                    if archivo_revision and archivo_revision.filename:
                        ruta_revision, nombre_revision = guardar_archivo_subido(
                            archivo_revision,
                            'tareas_revision',
                            f'revision_tarea_{id_tarea}_al_{id_alumno}'
                        )
                        entrega_registro.archivo_revision_ruta = ruta_revision
                        entrega_registro.archivo_revision_nombre = nombre_revision
                        entrega_registro.fecha_revision = datetime.utcnow()

                if value.strip() == '':
                    continue

                try:
                    calificacion = float(value)
                except ValueError:
                    continue

                if calificacion < 0 or calificacion > puntaje_maximo:
                    flash(f"La nota ingresada supera el puntaje maximo de la tarea ({puntaje_maximo} pts).", "warning")
                    return redirect(url_for('registrar_notas', id_grado=id_grado))

                alumno_db = Alumnos.query.get(id_alumno)
                if not alumno_db:
                    continue

                nota_existente = Notas.query.filter_by(id_alumno=alumno_db.id_alumno, id_tarea=id_tarea).first()
                
                if nota_existente:
                    nota_existente.calificacion = calificacion
                    nota_existente.id_maestro_autor = perfil.id_maestro
                    nota_existente.fecha_modificacion = datetime.utcnow()
                else:
                    nueva_nota = Notas(
                        id_tarea=id_tarea,
                        id_alumno=alumno_db.id_alumno,
                        calificacion=calificacion,
                        id_maestro_autor=perfil.id_maestro
                    ) 
                    db.session.add(nueva_nota)
            try:
                db.session.commit()
                flash("Calificaciones guardadas correctamente", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error al guardar calificaciones.", "danger")
                
        return redirect(url_for('registrar_notas', id_grado=id_grado))


    # 2. LÓGICA PARA MOSTRAR LAS TAREAS Y ENTREGAS (MÉTODO GET)
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    alumnos_lista = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()

    clases_maestro = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all()
    ids_clases = [c.id_clase for c in clases_maestro]
    tareas_db = Tareas.query.filter(Tareas.id_clase.in_(ids_clases)).order_by(Tareas.fecha_entrega.desc()).all()

    tareas_para_html = []
    
    for tarea in tareas_db:
        entregas = []
        for usuario_al in alumnos_lista:
            alumno_perfil = Alumnos.query.filter_by(id_usuario=usuario_al.id_usuario).first()
            
            entrega_registro = EntregasTareas.query.filter_by(id_alumno=alumno_perfil.id_alumno, id_tarea=tarea.id_tarea).first()
            nota_registro = Notas.query.filter_by(id_alumno=alumno_perfil.id_alumno, id_tarea=tarea.id_tarea).first()
            
            estado_entrega = entrega_registro.estado if entrega_registro else 'Pendiente'
            archivo_url = (
                url_for('static', filename=entrega_registro.archivo_ruta.replace('static/', ''))
                if (entrega_registro and entrega_registro.archivo_ruta) else None
            )
            archivo_revision_url = (
                url_for('static', filename=entrega_registro.archivo_revision_ruta.replace('static/', ''))
                if (entrega_registro and entrega_registro.archivo_revision_ruta) else None
            )
            
            entregas.append({
                'alumno': usuario_al,
                'id_alumno': alumno_perfil.id_alumno,
                'estado': estado_entrega,
                'archivo_url': archivo_url,
                'archivo_nombre': entrega_registro.archivo_nombre if entrega_registro else None,
                'comentario_alumno': entrega_registro.comentario_alumno if entrega_registro else '',
                'comentario_maestro': entrega_registro.comentario_maestro if entrega_registro else '',
                'archivo_revision_url': archivo_revision_url,
                'archivo_revision_nombre': entrega_registro.archivo_revision_nombre if entrega_registro else None,
                'nota': nota_registro.calificacion if nota_registro else ''
            })
            
        tareas_para_html.append({
            'id_tarea': tarea.id_tarea,
            'titulo': tarea.titulo,
            'descripcion': tarea.descripcion, 
            'periodo': tarea.periodo or 'Sin periodo',
            'puntos': float(tarea.puntos or 0),
            'fecha_entrega': tarea.fecha_entrega.strftime('%d/%m/%Y %H:%M') if tarea.fecha_entrega else 'Sin fecha',
            'archivo_adjunto_url': (
                url_for('static', filename=tarea.archivo_adjunto_ruta.replace('static/', ''))
                if tarea.archivo_adjunto_ruta else None
            ),
            'archivo_adjunto_nombre': tarea.archivo_adjunto_nombre,
            'entregas': entregas
        })

    return render_template('Panel_Maestro/notas_subir.html', tareas=tareas_para_html, id_grado=id_grado, grado=grado)

# --- OTROS MÓDULOS ---

@app.route('/maestro/grados/ver')
def ver_grados():
    if session.get('rol') != 2: return redirect(url_for('login'))
    return render_template('Panel_Maestro/grados.html')

@app.route('/maestro/grado/<int:id_grado>')
def gestionar_grado(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    alumnos = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()
    grado = Grados.query.get_or_404(id_grado)
    return render_template('Panel_Maestro/maestro_gestion_grado.html', grado=grado, alumnos=alumnos)

@app.route('/maestro/grado/<int:id_grado>/contenidos', methods=['GET', 'POST'])
def maestro_contenidos_clase(id_grado):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    grado = Grados.query.get_or_404(id_grado)
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).order_by(Clases.nombre_clase.asc()).all() if perfil else []

    if request.method == 'POST':
        tipo = request.form.get('tipo_contenido')
        clase = maestro_posee_clase(perfil, request.form.get('id_clase'), id_grado)

        if not clase:
            flash('La clase seleccionada no pertenece a este maestro.', 'danger')
            return redirect(url_for('maestro_contenidos_clase', id_grado=id_grado))

        try:
            if tipo == 'documento':
                archivo = request.files.get('archivo')
                if not archivo or archivo.filename == '':
                    flash('Debes seleccionar un archivo para el documento.', 'warning')
                    return redirect(url_for('maestro_contenidos_clase', id_grado=id_grado))

                filename = secure_filename(archivo.filename)
                os.makedirs('static/uploads/documentos_clase', exist_ok=True)
                ruta_guardado = os.path.join('static/uploads/documentos_clase', filename)
                archivo.save(ruta_guardado)

                item = DocumentosClase(
                    id_clase=clase.id_clase,
                    titulo=request.form.get('titulo'),
                    descripcion=request.form.get('descripcion'),
                    archivo_ruta=ruta_guardado,
                    id_usuario_autor=session.get('user_id')
                )
            elif tipo == 'enlace':
                item = EnlacesClase(
                    id_clase=clase.id_clase,
                    titulo=request.form.get('titulo'),
                    descripcion=request.form.get('descripcion'),
                    url=normalizar_url_externa(request.form.get('url')),
                    id_usuario_autor=session.get('user_id')
                )
            elif tipo == 'video':
                item = VideosClase(
                    id_clase=clase.id_clase,
                    titulo=request.form.get('titulo'),
                    descripcion=request.form.get('descripcion'),
                    url=normalizar_url_externa(request.form.get('url')),
                    id_usuario_autor=session.get('user_id')
                )
            else:
                flash('Tipo de contenido no valido.', 'warning')
                return redirect(url_for('maestro_contenidos_clase', id_grado=id_grado))

            db.session.add(item)
            db.session.commit()
            flash('Contenido publicado correctamente.', 'success')
        except Exception as exc:
            db.session.rollback()
            print(f'Error guardando contenido de clase: {exc}')
            flash('No se pudo guardar el contenido.', 'danger')

        return redirect(url_for('maestro_contenidos_clase', id_grado=id_grado))

    documentos = DocumentosClase.query.join(Clases).filter(
        Clases.id_maestro == perfil.id_maestro,
        Clases.id_grado == id_grado
    ).order_by(DocumentosClase.fecha_publicacion.desc()).all() if perfil else []
    enlaces = EnlacesClase.query.join(Clases).filter(
        Clases.id_maestro == perfil.id_maestro,
        Clases.id_grado == id_grado
    ).order_by(EnlacesClase.fecha_publicacion.desc()).all() if perfil else []
    videos = VideosClase.query.join(Clases).filter(
        Clases.id_maestro == perfil.id_maestro,
        Clases.id_grado == id_grado
    ).order_by(VideosClase.fecha_publicacion.desc()).all() if perfil else []

    return render_template(
        'Panel_Maestro/contenidos_clase.html',
        grado=grado,
        clases=clases,
        documentos=documentos,
        enlaces=enlaces,
        videos=videos
    )

@app.route('/maestro/grado/<int:id_grado>/foros', methods=['GET', 'POST'])
def maestro_foros_clase(id_grado):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    grado = Grados.query.get_or_404(id_grado)
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).order_by(Clases.nombre_clase.asc()).all() if perfil else []

    if request.method == 'POST':
        clase = maestro_posee_clase(perfil, request.form.get('id_clase'), id_grado)
        if not clase:
            flash('La clase seleccionada no pertenece a este maestro.', 'danger')
            return redirect(url_for('maestro_foros_clase', id_grado=id_grado))

        try:
            foro = ForosClase(
                id_clase=clase.id_clase,
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                id_usuario_autor=session.get('user_id')
            )
            db.session.add(foro)
            db.session.commit()
            flash('Tema de foro publicado correctamente.', 'success')
        except Exception as exc:
            db.session.rollback()
            print(f'Error guardando foro de clase: {exc}')
            flash('No se pudo publicar el foro.', 'danger')

        return redirect(url_for('maestro_foros_clase', id_grado=id_grado))

    foros = ForosClase.query.join(Clases).filter(
        Clases.id_maestro == perfil.id_maestro,
        Clases.id_grado == id_grado
    ).order_by(ForosClase.fecha_publicacion.desc()).all() if perfil else []

    autores_ids = list({foro.id_usuario_autor for foro in foros if foro.id_usuario_autor})
    autores = {
        usuario.id_usuario: usuario
        for usuario in Usuarios.query.filter(Usuarios.id_usuario.in_(autores_ids or [0])).all()
    }

    return render_template(
        'Panel_Maestro/foros_clase.html',
        grado=grado,
        clases=clases,
        foros=foros,
        autores=autores
    )

@app.route('/maestro/foro/<int:id_foro>', methods=['GET', 'POST'])
def maestro_foro_detalle(id_foro):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    foro = ForosClase.query.get_or_404(id_foro)
    clase_obj = Clases.query.get_or_404(foro.id_clase)
    if not perfil or clase_obj.id_maestro != perfil.id_maestro:
        flash('No tienes acceso a este foro.', 'danger')
        return redirect(url_for('maestro_dashboard'))

    if request.method == 'POST':
        contenido = (request.form.get('contenido') or '').strip()
        if contenido:
            mensaje = MensajesForoClase(
                id_foro=foro.id_foro,
                id_usuario_autor=session.get('user_id'),
                contenido=contenido
            )
            db.session.add(mensaje)
            db.session.commit()
            flash('Tu respuesta fue publicada.', 'success')
        return redirect(url_for('maestro_foro_detalle', id_foro=id_foro))

    autores_ids = [foro.id_usuario_autor] + [mensaje.id_usuario_autor for mensaje in foro.mensajes if mensaje.id_usuario_autor]
    autores = {
        usuario.id_usuario: usuario
        for usuario in Usuarios.query.filter(Usuarios.id_usuario.in_(list({autor for autor in autores_ids if autor}) or [0])).all()
    }

    return render_template(
        'Panel_Maestro/foro_detalle.html',
        foro=foro,
        clase=clase_obj,
        autores=autores
    )

@app.route('/maestro/anuncios/<int:id_grado>', methods=['GET', 'POST'])
def maestro_anuncios(id_grado):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    grado = Grados.query.get_or_404(id_grado)
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []

    if request.method == 'POST':
        nuevo_anuncio = Anuncios(
            titulo=request.form.get('titulo'),
            contenido=request.form.get('mensaje'),
            dirigido_a=f'Grado_{id_grado}',
            id_usuario_autor=session.get('user_id'),
            id_clase=request.form.get('id_clase') or None
        )
        db.session.add(nuevo_anuncio)
        db.session.commit()
        flash('Anuncio publicado correctamente.', 'success')
        return redirect(url_for('maestro_anuncios', id_grado=id_grado))

    return render_template('Panel_Maestro/anuncios.html', grado=grado, clases=clases)

@app.route('/maestro/examenes/revision/<int:id_grado>', methods=['GET', 'POST'])
def revisar_examenes(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    grado = Grados.query.get_or_404(id_grado)

    # 1. LÓGICA POST (Guardar Notas)
    if request.method == 'POST':
        # Obtenemos el id_examen del parámetro de la URL (?id_examen=X)
        id_ex_form = request.args.get('id_examen')
        
        if id_ex_form:
            examen_obj = Examenes.query.join(Clases, Clases.id_clase == Examenes.id_clase).filter(
                Examenes.id_examen == id_ex_form,
                Clases.id_maestro == perfil.id_maestro
            ).first()

            if not examen_obj:
                flash("El examen seleccionado no pertenece a este maestro.", "danger")
                return redirect(url_for('revisar_examenes', id_grado=id_grado))

            puntaje_maximo = float(examen_obj.puntos_maximos or 0)

            for key, value in request.form.items():
                if key.startswith('nota_') and value.strip() != '':
                    id_al_entregue = int(key.split('_')[1])
                    
                    # Buscamos si ya tiene nota registrada
                    nota_existente = Notas.query.filter_by(
                        id_alumno=id_al_entregue, 
                        id_examen=id_ex_form
                    ).first()
                    
                    try:
                        val_nota = float(value)
                        if val_nota < 0 or val_nota > puntaje_maximo:
                            flash(f"La nota ingresada supera el puntaje maximo del examen ({puntaje_maximo} pts).", "warning")
                            return redirect(url_for('revisar_examenes', id_grado=id_grado))

                        if nota_existente:
                            nota_existente.calificacion = val_nota
                            nota_existente.id_maestro_autor = perfil.id_maestro
                            nota_existente.fecha_modificacion = datetime.utcnow()
                        else:
                            nueva_nota = Notas(
                                id_examen=id_ex_form,
                                id_alumno=id_al_entregue,
                                calificacion=val_nota,
                                id_maestro_autor=perfil.id_maestro
                            )
                            db.session.add(nueva_nota)
                            
                        # OPCIONAL: Actualizar el estado en la tabla entregas_examenes a 'Calificado'
                        entrega_obj = EntregasExamenes.query.filter_by(
                            id_alumno=id_al_entregue, 
                            id_examen=id_ex_form
                        ).first()
                        if entrega_obj:
                            entrega_obj.estado = 'Calificado'

                    except ValueError:
                        continue 

            db.session.commit()
            flash("Calificaciones guardadas correctamente.", "success")
        return redirect(url_for('revisar_examenes', id_grado=id_grado))

    # 2. LÓGICA GET (Cargar Datos)
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    
    # Obtenemos los alumnos de esas secciones
    alumnos_lista = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()

    # Filtramos exámenes por las clases del maestro en este grado
    clases_maestro = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all()
    ids_clases = [c.id_clase for c in clases_maestro]
    
    examenes_db = Examenes.query.filter(Examenes.id_clase.in_(ids_clases)).order_by(Examenes.fecha_limite.desc()).all()

    examenes_data = []
    for ex in examenes_db:
        entregas = []
        for u_al in alumnos_lista:
            # Obtenemos el perfil de alumno para tener el id_alumno (no el id_usuario)
            al_perfil = Alumnos.query.filter_by(id_usuario=u_al.id_usuario).first()
            if not al_perfil: continue
            
            # Consultamos entrega y nota (Asegúrate que el modelo EntregasExamenes ya esté corregido)
            entrega = EntregasExamenes.query.filter_by(id_alumno=al_perfil.id_alumno, id_examen=ex.id_examen).first()
            nota = Notas.query.filter_by(id_alumno=al_perfil.id_alumno, id_examen=ex.id_examen).first()
            
            entregas.append({
                'alumno': u_al,
                'id_alumno': al_perfil.id_alumno,
                'estado': entrega.estado if entrega else 'Pendiente',
                'archivo': entrega.archivo_ruta if entrega else None,
                'respuestas': entrega.respuestas_json if entrega else None,
                'nota': nota.calificacion if nota else ''
            })
        
        examenes_data.append({
            'info': ex,
            'entregas': entregas
        })

    return render_template('Panel_Maestro/examenes_revisar.html', examenes=examenes_data, grado=grado)

# ==============================================================================
# ---------------------- RUTAS PARA ASIGNAR EXÁMENES (NUEVO) -------------------
# ==============================================================================

# 1. Menú principal de selección
@app.route('/maestro/grado/<int:id_grado>/nuevo_examen')
def vista_nuevo_examen(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    return render_template('Panel_Maestro/nuevo_examen.html', id_grado=id_grado, grado=grado, periodos=obtener_periodos_disponibles())

# 2. Interfaz: Subir Archivo
@app.route('/maestro/grado/<int:id_grado>/nuevo_examen/archivo', methods=['GET', 'POST'])
def examen_archivo(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    
    # Obtener las materias del maestro para el menú desplegable
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []

    if request.method == 'POST':
        try:
            archivo = request.files.get('archivo')
            archivo_ruta = None
            if archivo and archivo.filename != '':
                filename = secure_filename(archivo.filename)
                # Crea la carpeta si no existe y guarda el archivo
                os.makedirs('static/uploads/examenes', exist_ok=True)
                archivo_ruta = os.path.join('static/uploads/examenes', filename)
                archivo.save(archivo_ruta)

            nuevo_examen = Examenes(
                id_clase=request.form.get('id_clase'),
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                periodo=request.form.get('periodo'),
                modalidad='archivo',
                archivo_ruta=archivo_ruta,
                fecha_limite=datetime.strptime(request.form.get('fecha_limite'), '%Y-%m-%dT%H:%M') if request.form.get('fecha_limite') else None,
                puntos_maximos=float(request.form.get('puntos_maximos', 100))
            )
            db.session.add(nuevo_examen)
            db.session.commit()
            flash("Examen tipo archivo creado exitosamente", "success")
            return redirect(url_for('gestionar_grado', id_grado=id_grado))
        except Exception as e:
            db.session.rollback()
            print(f"Error guardando examen de archivo: {e}")
            flash("Error al crear el examen. Revisa los datos.", "danger")

    return render_template('Panel_Maestro/examen_archivo.html', id_grado=id_grado, grado=grado, clases=clases, periodos=obtener_periodos_disponibles())

# 3. Interfaz: Solo Instrucciones
@app.route('/maestro/grado/<int:id_grado>/nuevo_examen/instrucciones', methods=['GET', 'POST'])
def examen_instrucciones(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []

    if request.method == 'POST':
        try:
            nuevo_examen = Examenes(
                id_clase=request.form.get('id_clase'),
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                periodo=request.form.get('periodo'),
                modalidad='instrucciones',
                fecha_limite=datetime.strptime(request.form.get('fecha_limite'), '%Y-%m-%dT%H:%M') if request.form.get('fecha_limite') else None,
                puntos_maximos=float(request.form.get('puntos_maximos', 100))
            )
            db.session.add(nuevo_examen)
            db.session.commit()
            flash("Examen de instrucciones creado exitosamente", "success")
            return redirect(url_for('gestionar_grado', id_grado=id_grado))
        except Exception as e:
            db.session.rollback()
            print(f"Error guardando examen de instrucciones: {e}")
            flash("Error al crear el examen.", "danger")

    return render_template('Panel_Maestro/examen_instrucciones.html', id_grado=id_grado, grado=grado, clases=clases, periodos=obtener_periodos_disponibles())

# 4. Interfaz: Formulario/Cuestionario manual (CORREGIDO Y COMPLETO)
@app.route('/maestro/grado/<int:id_grado>/nuevo_examen/formulario', methods=['GET', 'POST'])
def examen_formulario(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro, id_grado=id_grado).all() if perfil else []

    if request.method == 'POST':
        try:
            # Primero guardamos la cabecera del examen (Título, puntos, etc)
            nuevo_examen = Examenes(
                id_clase=request.form.get('id_clase'),
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                periodo=request.form.get('periodo'),
                modalidad='formulario',
                fecha_limite=datetime.strptime(request.form.get('fecha_limite'), '%Y-%m-%dT%H:%M') if request.form.get('fecha_limite') else None,
                puntos_maximos=float(request.form.get('puntos_maximos', 100))
            )
            db.session.add(nuevo_examen)
            db.session.flush() # Nos permite obtener el ID del examen antes del commit final

            # Procesar las preguntas dinámicas
            total_preguntas = int(request.form.get('total_preguntas', 0))

            for i in range(1, total_preguntas + 1):
                texto_pregunta = request.form.get(f'pregunta_{i}')
                
                if texto_pregunta: # Verificamos si la pregunta existe
                    tipo_pregunta = request.form.get(f'tipo_pregunta_{i}')
                    puntos = float(request.form.get(f'puntos_pregunta_{i}', 1.0))

                    nueva_pregunta = PreguntasExamen(
                        id_examen=nuevo_examen.id_examen,
                        texto_pregunta=texto_pregunta,
                        tipo_pregunta='opcion_multiple' if tipo_pregunta == 'opciones' else 'abierta',
                        puntos=puntos
                    )
                    db.session.add(nueva_pregunta)
                    db.session.flush() # Obtenemos el ID de la pregunta

                    # Guardamos las opciones si es de opción múltiple
                    if tipo_pregunta == 'opciones':
                        opciones_ids = request.form.getlist(f'ids_opciones_{i}[]')
                        correcta_id = request.form.get(f'correcta_pregunta_{i}') 

                        for unique_id in opciones_ids:
                            texto_opcion = request.form.get(f'opcion_texto_{i}_{unique_id}')
                            es_correcta = (unique_id == correcta_id)

                            nueva_opcion = OpcionesPregunta(
                                id_pregunta=nueva_pregunta.id_pregunta,
                                texto_opcion=texto_opcion,
                                es_correcta=es_correcta
                            )
                            db.session.add(nueva_opcion)

            db.session.commit()
            flash("Cuestionario creado exitosamente", "success")
            return redirect(url_for('gestionar_grado', id_grado=id_grado))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error guardando cuestionario: {e}")
            flash("Error al crear el cuestionario.", "danger")

    return render_template('Panel_Maestro/examen_formulario.html', id_grado=id_grado, grado=grado, clases=clases, periodos=obtener_periodos_disponibles())
# ----------------------------------------

@app.route('/maestro/reportes/enviar/<int:id_grado>')
def enviar_reportes(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    return render_template('Panel_Maestro/reportes_enviar.html', id_grado=id_grado, grado=grado)

@app.route('/maestro/asistencia/control/<int:id_grado>')
def control_asistencia(id_grado):
    if session.get('rol') != 2: 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    grado = Grados.query.get_or_404(id_grado)
    clases_asistencia = Clases.query.filter_by(
        id_maestro=perfil.id_maestro,
        id_grado=id_grado
    ).order_by(Clases.nombre_clase.asc()).all() if perfil else []
    id_clase_seleccionada = request.args.get('id_clase', type=int)

    clase_asistencia = None
    if clases_asistencia:
        clase_asistencia = next(
            (clase for clase in clases_asistencia if clase.id_clase == id_clase_seleccionada),
            clases_asistencia[0]
        )
    
    # Obtener alumnos del grado
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    alumnos_usuarios = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()
    
    # Preparamos la lista de alumnos
    alumnos_data = []
    for au in alumnos_usuarios:
        perfil_alumno = Alumnos.query.filter_by(id_usuario=au.id_usuario).first()
        alumnos_data.append({
            'usuario': au,
            'id_alumno': perfil_alumno.id_alumno
        })

    asistencia_guardada = {}
    if clase_asistencia and alumnos_data:
        ids_alumnos = [alumno['id_alumno'] for alumno in alumnos_data]
        asistencias_db = Asistencias.query.filter(
            Asistencias.id_clase == clase_asistencia.id_clase,
            Asistencias.id_alumno.in_(ids_alumnos)
        ).all()

        estado_a_codigo = {
            'Presente': 'P',
            'Ausente': 'A',
            'Excusa': 'E',
            'Feriado': 'F'
        }
        for asistencia in asistencias_db:
            fecha_str = asistencia.fecha.strftime('%Y-%m-%d') if asistencia.fecha else ''
            asistencia_guardada[f"{asistencia.id_alumno}|{fecha_str}"] = estado_a_codigo.get(asistencia.estado, '-')
            
    return render_template(
        'Panel_Maestro/asistencia.html',
        grado=grado,
        alumnos=alumnos_data,
        clases_asistencia=clases_asistencia,
        clase_asistencia=clase_asistencia,
        asistencia_guardada=asistencia_guardada
    )

@app.route('/maestro/asistencia/guardar', methods=['POST'])
def guardar_asistencia():
    if session.get('rol') != 2:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    data = request.get_json(silent=True) or {}
    id_alumno = data.get('id_alumno')
    id_clase = data.get('id_clase')
    fecha = data.get('fecha')
    estado_codigo = data.get('estado')

    if not id_alumno or not id_clase or not fecha:
        return jsonify({'ok': False, 'error': 'Datos incompletos'}), 400

    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'error': 'Fecha invalida'}), 400

    estado_map = {
        'P': 'Presente',
        'A': 'Ausente',
        'E': 'Excusa',
        'F': 'Feriado'
    }

    asistencia = Asistencias.query.filter_by(
        id_clase=id_clase,
        id_alumno=id_alumno,
        fecha=fecha_obj
    ).first()

    if estado_codigo == '-' or not estado_codigo:
        if asistencia:
            db.session.delete(asistencia)
            db.session.commit()
        return jsonify({'ok': True})

    estado_db = estado_map.get(estado_codigo)
    if not estado_db:
        return jsonify({'ok': False, 'error': 'Estado invalido'}), 400

    if asistencia:
        asistencia.estado = estado_db
    else:
        asistencia = Asistencias(
            id_clase=id_clase,
            id_alumno=id_alumno,
            fecha=fecha_obj,
            estado=estado_db
        )
        db.session.add(asistencia)

    db.session.commit()
    return jsonify({'ok': True})

@app.route('/maestro/datos/exportar')
def exportar_datos():
    if session.get('rol') != 2: return redirect(url_for('login'))
    return "Módulo para Exportar Datos. (Pendiente HTML)"


# ==============================================================================
# ------------------------------ PANEL DE ALUMNO -------------------------------
# ==============================================================================


@app.route('/alumno')
def alumno_dashboard():
    if session.get('rol') != 3: 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    if not alumno:
        return "Perfil de alumno no encontrado", 404

    ciclo_activo = CiclosLectivos.query.filter_by(estado='ACTIVO').first()
    clases_alumno = Clases.query.options(
        joinedload(Clases.maestro_titular).joinedload(Maestros.usuario)
    ).filter_by(id_grado=alumno.seccion.id_grado).all()
    ids_clases = [c.id_clase for c in clases_alumno]

    ahora = datetime.utcnow()
    limite_semana = ahora + timedelta(days=7)
    entregadas_ids = {
        entrega.id_tarea for entrega in EntregasTareas.query.filter_by(id_alumno=alumno.id_alumno).all()
    }
    tareas_proximas = Tareas.query.options(joinedload(Tareas.clase)).filter(
        Tareas.id_clase.in_(ids_clases),
        Tareas.fecha_entrega >= ahora,
        Tareas.fecha_entrega <= limite_semana
    ).order_by(Tareas.fecha_entrega.asc()).all()
    tareas_proximas = [tarea for tarea in tareas_proximas if tarea.id_tarea not in entregadas_ids][:5]

    asistencias = Asistencias.query.filter_by(id_alumno=alumno.id_alumno).all()
    total_a = len(asistencias)
    presentes = len([a for a in asistencias if a.estado == 'Presente'])
    porcentaje_asistencia = round((presentes / total_a * 100)) if total_a > 0 else 0

    resumen_notas = construir_resumen_notas_alumno(alumno)
    rendimiento = construir_rendimiento_dashboard(resumen_notas)
    progreso_ciclo = construir_progreso_ciclo(ciclo_activo)
    clases_hoy = construir_clases_hoy_alumno(alumno)
    comunicados = construir_comunicados_alumno(alumno)

    return render_template('Panel_Alumno/alumno_dash.html', 
                           alumno=alumno,
                           anuncios=comunicados, 
                           tareas=tareas_proximas,
                           asistencia_val=porcentaje_asistencia,
                           promedio_val=rendimiento['promedio_actual'],
                           rendimiento=rendimiento,
                           rendimiento_periodos=resumen_notas['periodos'][:3],
                           progreso_ciclo=progreso_ciclo,
                           clases_hoy=clases_hoy,
                           ciclo_activo=ciclo_activo,
                           total_materias=len(clases_alumno),
                           datetime=datetime)

@app.route('/alumno/clases')
def alumno_clases():
    if session.get('rol') != 3: 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    if not alumno:
        return "Perfil no encontrado", 404

    clases = Clases.query.filter_by(id_grado=alumno.seccion.id_grado).all()

    return render_template('Panel_Alumno/mis_clases.html', 
                           clases=clases, 
                           alumno=alumno)

# --- FUNCIÓN AUXILIAR (Para evitar redundancia) ---
def obtener_color_materia(alumno, id_clase):
    colors = ['#4361ee', '#2ecc71', '#ff9f43', '#9b59b6', '#e74c3c', '#00bcd4']
    # Buscamos las clases del mismo grado del alumno para que el índice coincida
    todas_las_clases_grado = Clases.query.filter_by(id_grado=alumno.seccion.id_grado).all()
    
    for index, c in enumerate(todas_las_clases_grado):
        if c.id_clase == id_clase:
            return colors[index % len(colors)]
    return colors[0]


def normalizar_nombre_periodo(nombre_periodo):
    return (nombre_periodo or '').strip().lower()


def porcentaje_desde_nota(calificacion, puntaje_maximo):
    try:
        valor = float(calificacion)
    except (TypeError, ValueError):
        return None

    try:
        maximo = float(puntaje_maximo)
    except (TypeError, ValueError):
        maximo = 0

    if maximo > 0:
        return round((valor / maximo) * 100, 1)

    if 0 <= valor <= 100:
        return round(valor, 1)

    return None


def calcular_componente_periodo(registros):
    if not registros:
        return None

    total_obtenido = 0.0
    total_maximo = 0.0

    for registro in registros:
        try:
            valor = float(registro['calificacion'])
        except (TypeError, ValueError):
            continue

        try:
            maximo = float(registro['puntaje_maximo'])
        except (TypeError, ValueError):
            maximo = 0.0

        if maximo > 0:
            total_obtenido += valor
            total_maximo += maximo

    if total_maximo > 0:
        return round((total_obtenido / total_maximo) * 100, 1)

    porcentajes = [
        registro['porcentaje']
        for registro in registros
        if registro.get('porcentaje') is not None
    ]
    if porcentajes:
        return round(sum(porcentajes) / len(porcentajes), 1)

    return None


def construir_resumen_notas_alumno(alumno):
    clases = Clases.query.options(
        joinedload(Clases.maestro_titular).joinedload(Maestros.usuario)
    ).filter_by(id_grado=alumno.seccion.id_grado).all()

    notas = Notas.query.options(
        joinedload(Notas.tarea).joinedload(Tareas.clase),
        joinedload(Notas.examen).joinedload(Examenes.clase),
        joinedload(Notas.maestro_autor).joinedload(Maestros.usuario)
    ).filter_by(id_alumno=alumno.id_alumno).all()

    periodos_disponibles = obtener_periodos_disponibles()
    periodos_ordenados = []
    periodos_agregados = set()

    for periodo in periodos_disponibles:
        clave = normalizar_nombre_periodo(periodo.nombre_periodo)
        if not clave or clave in periodos_agregados:
            continue
        periodos_ordenados.append({
            'id_periodo': periodo.id_periodo,
            'nombre': periodo.nombre_periodo,
            'clave': clave
        })
        periodos_agregados.add(clave)

    notas_por_periodo_y_clase = defaultdict(lambda: defaultdict(lambda: {'tareas': [], 'examenes': []}))

    for nota in notas:
        actividad = nota.tarea or nota.examen
        if not actividad:
            continue

        clase = actividad.clase if hasattr(actividad, 'clase') else None
        if not clase:
            continue

        nombre_periodo = getattr(actividad, 'periodo', None)
        clave_periodo = normalizar_nombre_periodo(nombre_periodo)
        if not clave_periodo:
            continue

        if clave_periodo not in periodos_agregados:
            periodos_ordenados.append({
                'id_periodo': None,
                'nombre': nombre_periodo.strip(),
                'clave': clave_periodo
            })
            periodos_agregados.add(clave_periodo)

        es_tarea = nota.tarea is not None
        puntaje_maximo = actividad.puntos if es_tarea else actividad.puntos_maximos
        item = {
            'id_nota': nota.id_nota,
            'id_actividad': actividad.id_tarea if es_tarea else actividad.id_examen,
            'titulo': actividad.titulo,
            'tipo': 'Acumulativo' if es_tarea else 'Examen',
            'calificacion': float(nota.calificacion),
            'puntaje_maximo': float(puntaje_maximo or 0),
            'porcentaje': porcentaje_desde_nota(nota.calificacion, puntaje_maximo),
            'fecha': nota.fecha_modificacion,
            'maestro': (
                f"{nota.maestro_autor.usuario.nombre} {nota.maestro_autor.usuario.apellido}"
                if nota.maestro_autor and nota.maestro_autor.usuario else 'Sin asignar'
            )
        }

        bucket = notas_por_periodo_y_clase[clave_periodo][clase.id_clase]
        if es_tarea:
            bucket['tareas'].append(item)
        else:
            bucket['examenes'].append(item)

    resumen_periodos = []
    promedios_periodo = []

    for indice, periodo in enumerate(periodos_ordenados):
        clases_periodo = []
        promedios_clase = []

        for clase in clases:
            bucket = notas_por_periodo_y_clase[periodo['clave']].get(clase.id_clase, {'tareas': [], 'examenes': []})
            acumulativo = calcular_componente_periodo(bucket['tareas'])
            examen = calcular_componente_periodo(bucket['examenes'])

            componentes = [valor for valor in (acumulativo, examen) if valor is not None]
            nota_general = round(sum(componentes) / len(componentes), 1) if componentes else None

            if nota_general is not None:
                promedios_clase.append(nota_general)

            clases_periodo.append({
                'id_clase': clase.id_clase,
                'nombre_clase': clase.nombre_clase,
                'color': obtener_color_materia(alumno, clase.id_clase),
                'maestro': (
                    f"{clase.maestro_titular.usuario.nombre} {clase.maestro_titular.usuario.apellido}"
                    if clase.maestro_titular and clase.maestro_titular.usuario else 'Sin maestro asignado'
                ),
                'acumulativo': acumulativo,
                'examen': examen,
                'nota_general': nota_general,
                'tareas': sorted(bucket['tareas'], key=lambda item: item['fecha'] or datetime.min, reverse=True),
                'examenes': sorted(bucket['examenes'], key=lambda item: item['fecha'] or datetime.min, reverse=True)
            })

        promedio_periodo = round(sum(promedios_clase) / len(promedios_clase), 1) if promedios_clase else None
        if promedio_periodo is not None:
            promedios_periodo.append(promedio_periodo)

        resumen_periodos.append({
            'id': f"periodo-{indice}",
            'nombre': periodo['nombre'],
            'promedio': promedio_periodo,
            'clases': clases_periodo,
            'clases_con_nota': len(promedios_clase)
        })

    promedio_final = round(sum(promedios_periodo) / len(promedios_periodo), 1) if promedios_periodo else None

    return {
        'periodos': resumen_periodos,
        'promedio_final': promedio_final,
        'periodos_evaluados': len(promedios_periodo),
        'total_clases': len(clases)
    }


def construir_progreso_ciclo(ciclo_activo):
    if not ciclo_activo:
        return {
            'porcentaje': 0,
            'texto': 'Sin ciclo activo',
            'detalle': 'Esperando configuración académica'
        }

    hoy = datetime.now().date()
    inicio = ciclo_activo.fecha_inicio
    fin = ciclo_activo.fecha_fin

    if inicio and fin and fin > inicio:
        total_dias = (fin - inicio).days
        transcurridos = min(max((hoy - inicio).days, 0), total_dias)
        porcentaje = round((transcurridos / total_dias) * 100) if total_dias > 0 else 0
        return {
            'porcentaje': porcentaje,
            'texto': f'{porcentaje}%',
            'detalle': f'{ciclo_activo.nombre_ciclo}'
        }

    if inicio:
        inicio_ano = inicio.replace(month=1, day=1)
        fin_ano = inicio.replace(month=12, day=31)
        total_dias = (fin_ano - inicio_ano).days or 1
        transcurridos = min(max((hoy - inicio_ano).days, 0), total_dias)
        porcentaje = round((transcurridos / total_dias) * 100)
        return {
            'porcentaje': porcentaje,
            'texto': f'{porcentaje}%',
            'detalle': f'{ciclo_activo.nombre_ciclo}'
        }

    return {
        'porcentaje': 15,
        'texto': 'Activo',
        'detalle': f'{ciclo_activo.nombre_ciclo}'
    }


def construir_clases_hoy_alumno(alumno):
    hoy = datetime.now().date()
    if hoy.weekday() > 4:
        return {
            'dia_label': 'Fin de semana',
            'bloques': []
        }

    dia_actual = DIA_ORDEN[hoy.weekday()]
    bloques = Horarios.query.options(
        joinedload(Horarios.clase).joinedload(Clases.maestro_titular).joinedload(Maestros.usuario)
    ).filter_by(
        id_seccion=alumno.id_seccion,
        dia_semana=dia_actual
    ).order_by(Horarios.hora_inicio.asc()).all()

    asistencias_hoy = Asistencias.query.filter(
        Asistencias.id_alumno == alumno.id_alumno,
        Asistencias.fecha == hoy,
        Asistencias.id_clase.in_([bloque.id_clase for bloque in bloques] or [0])
    ).all()
    asistencias_map = {asistencia.id_clase: asistencia.estado for asistencia in asistencias_hoy}

    colores_base = ['#4361ee', '#2ecc71', '#ff9f43', '#9b59b6', '#e74c3c', '#0ea5e9', '#14b8a6']
    bloques_data = []
    for indice, bloque in enumerate(bloques):
        estado = asistencias_map.get(bloque.id_clase, 'Sin registro')
        estado_ui = ESTADOS_ASISTENCIA_UI.get(estado, ESTADOS_ASISTENCIA_UI['Sin registro'])
        bloques_data.append({
            'id_clase': bloque.id_clase,
            'materia': bloque.clase.nombre_clase if bloque.clase else 'Clase',
            'maestro': (
                f"{bloque.clase.maestro_titular.usuario.nombre} {bloque.clase.maestro_titular.usuario.apellido}"
                if bloque.clase and bloque.clase.maestro_titular and bloque.clase.maestro_titular.usuario else 'Maestro pendiente'
            ),
            'hora': describir_rango_hora(bloque.hora_inicio, bloque.hora_fin),
            'accent': colores_base[indice % len(colores_base)],
            'estado': estado,
            'estado_ui': estado_ui
        })

    return {
        'dia_label': DIA_LABELS[dia_actual],
        'bloques': bloques_data
    }


def construir_rendimiento_dashboard(resumen_notas):
    periodos = resumen_notas.get('periodos', [])
    periodos_con_promedio = [p for p in periodos if p.get('promedio') is not None]
    periodo_actual = periodos_con_promedio[-1] if periodos_con_promedio else (periodos[-1] if periodos else None)
    return {
        'periodo_actual': periodo_actual,
        'promedio_actual': round((periodo_actual.get('promedio') or 0), 1) if periodo_actual else 0,
        'texto_periodo': periodo_actual['nombre'] if periodo_actual else 'Sin parciales',
        'periodos_totales': len(periodos_con_promedio)
    }


def construir_comunicados_alumno(alumno):
    anuncios = Anuncios.query.options(
        joinedload(Anuncios.clase)
    ).filter(
        (
            (Anuncios.id_clase == None) &
            (
                Anuncios.dirigido_a.in_(['Todos', 'Alumnos']) |
                (Anuncios.dirigido_a == f'Grado_{alumno.seccion.id_grado}')
            )
        ) |
        (
            Anuncios.id_clase.in_(
                db.session.query(Clases.id_clase).filter_by(id_grado=alumno.seccion.id_grado)
            )
        )
    ).order_by(Anuncios.fecha_publicacion.desc()).limit(12).all()

    autores = {
        usuario.id_usuario: usuario
        for usuario in Usuarios.query.filter(
            Usuarios.id_usuario.in_([anuncio.id_usuario_autor for anuncio in anuncios if anuncio.id_usuario_autor] or [0])
        ).all()
    }

    comunicados = []
    for anuncio in anuncios:
        es_clase = anuncio.id_clase is not None and anuncio.clase is not None
        autor = autores.get(anuncio.id_usuario_autor)
        comunicados.append({
            'id_anuncio': anuncio.id_anuncio,
            'titulo': anuncio.titulo,
            'contenido': anuncio.contenido,
            'fecha': anuncio.fecha_publicacion,
            'autor': f"{autor.nombre} {autor.apellido}" if autor else 'Administración',
            'origen': anuncio.clase.nombre_clase if es_clase else 'Comunicado general',
            'es_clase': es_clase,
            'url': url_for('alumno_aula', id_clase=anuncio.id_clase) + '#anuncios' if es_clase else None
        })

    return comunicados


@app.route('/alumno/aula/<int:id_clase>')
def alumno_aula(id_clase):
    id_usuario_actual = session.get('user_id')
    if not id_usuario_actual:
        return redirect(url_for('login'))

    # Obtenemos objetos base
    alumno = Alumnos.query.filter_by(id_usuario=id_usuario_actual).first_or_404()
    clase_obj = Clases.query.get_or_404(id_clase)
    if not alumno_tiene_acceso_clase(alumno, clase_obj):
        flash('No tienes acceso a esta aula.', 'danger')
        return redirect(url_for('alumno_clases'))
    
    # Color consistente
    materia_color = obtener_color_materia(alumno, id_clase)

    # --- FILTRO DE ANUNCIOS DE CLASE ---
    # Solo traemos los anuncios que pertenecen a esta clase específica
    anuncios_clase = Anuncios.query.filter_by(id_clase=id_clase)\
                             .order_by(Anuncios.fecha_publicacion.desc()).all()

    # Tareas y validación de entregas
    tareas_clase = Tareas.query.filter_by(id_clase=id_clase).order_by(Tareas.fecha_entrega.asc()).all()
    resumen_aula = construir_resumen_aula(clase_obj, alumno)

    return render_template('/Panel_Alumno/Aula/Aula.html', 
                           clase=clase_obj, 
                           tareas=tareas_clase, 
                           entregadas_ids=resumen_aula['entregadas_ids'],
                           alumno=alumno,
                           materia_color=materia_color,
                           anuncios=anuncios_clase,
                           documentos=resumen_aula['documentos'],
                           enlaces=resumen_aula['enlaces'],
                           videos=resumen_aula['videos'],
                           foros=resumen_aula['foros'],
                           examenes=resumen_aula['examenes'],
                           examenes_entregados_ids=resumen_aula['examenes_entregados_ids']) # Variable para el aula

@app.route('/alumno/aula/<int:id_clase>/<string:categoria>')
def alumno_aula_categoria(id_clase, categoria):
    if session.get('rol') != 3:
        return redirect(url_for('login'))

    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first_or_404()
    clase_obj = Clases.query.get_or_404(id_clase)
    if not alumno_tiene_acceso_clase(alumno, clase_obj):
        flash('No tienes acceso a esta aula.', 'danger')
        return redirect(url_for('alumno_clases'))

    categoria_map = {
        'documentos': {'titulo': 'Documentos de Clase', 'icono': 'bi-folder2-open', 'template': 'Panel_Alumno/Aula/documentos.html'},
        'enlaces': {'titulo': 'Enlaces de Interes', 'icono': 'bi-link-45deg', 'template': 'Panel_Alumno/Aula/enlaces.html'},
        'videos': {'titulo': 'Videos de la Clase', 'icono': 'bi-play-btn-fill', 'template': 'Panel_Alumno/Aula/videos.html'},
        'foros': {'titulo': 'Foros de Clase', 'icono': 'bi-chat-dots-fill', 'template': 'Panel_Alumno/Aula/foros.html'},
        'examenes': {'titulo': 'Examenes de la Clase', 'icono': 'bi-patch-check-fill', 'template': 'Panel_Alumno/Aula/examenes.html'}
    }
    config = categoria_map.get(categoria)
    if not config:
        return redirect(url_for('alumno_aula', id_clase=id_clase))

    resumen_aula = construir_resumen_aula(clase_obj, alumno)
    materia_color = obtener_color_materia(alumno, id_clase)

    return render_template(
        config['template'],
        clase=clase_obj,
        alumno=alumno,
        materia_color=materia_color,
        categoria=categoria,
        categoria_titulo=config['titulo'],
        categoria_icono=config['icono'],
        documentos=resumen_aula['documentos'],
        enlaces=resumen_aula['enlaces'],
        videos=[{'item': video, 'embed_url': obtener_video_embed_url(video.url)} for video in resumen_aula['videos']],
        foros=resumen_aula['foros'],
        examenes=resumen_aula['examenes'],
        examenes_entregados_ids=resumen_aula['examenes_entregados_ids']
    )

@app.route('/alumno/aula/<int:id_clase>/foro/nuevo', methods=['POST'])
def alumno_crear_foro(id_clase):
    if session.get('rol') != 3:
        return redirect(url_for('login'))

    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first_or_404()
    clase_obj = Clases.query.get_or_404(id_clase)
    if not alumno_tiene_acceso_clase(alumno, clase_obj):
        flash('No tienes acceso a esta aula.', 'danger')
        return redirect(url_for('alumno_clases'))

    titulo = (request.form.get('titulo') or '').strip()
    descripcion = (request.form.get('descripcion') or '').strip()
    if titulo and descripcion:
        foro = ForosClase(
            id_clase=id_clase,
            titulo=titulo,
            descripcion=descripcion,
            id_usuario_autor=session.get('user_id')
        )
        db.session.add(foro)
        db.session.commit()
        flash('Tu tema fue publicado en el foro.', 'success')
    else:
        flash('Debes completar titulo y descripcion.', 'warning')

    return redirect(url_for('alumno_aula_categoria', id_clase=id_clase, categoria='foros'))

@app.route('/alumno/aula/foro/<int:id_foro>', methods=['GET', 'POST'])
def alumno_foro_detalle(id_foro):
    if session.get('rol') != 3:
        return redirect(url_for('login'))

    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first_or_404()
    foro = ForosClase.query.get_or_404(id_foro)
    clase_obj = Clases.query.get_or_404(foro.id_clase)
    if not alumno_tiene_acceso_clase(alumno, clase_obj):
        flash('No tienes acceso a este foro.', 'danger')
        return redirect(url_for('alumno_clases'))

    if request.method == 'POST':
        contenido = (request.form.get('contenido') or '').strip()
        if contenido:
            mensaje = MensajesForoClase(
                id_foro=foro.id_foro,
                id_usuario_autor=session.get('user_id'),
                contenido=contenido
            )
            db.session.add(mensaje)
            db.session.commit()
            flash('Tu respuesta fue publicada.', 'success')
        return redirect(url_for('alumno_foro_detalle', id_foro=id_foro))

    autores_ids = [foro.id_usuario_autor] + [mensaje.id_usuario_autor for mensaje in foro.mensajes if mensaje.id_usuario_autor]
    autores = {
        usuario.id_usuario: usuario
        for usuario in Usuarios.query.filter(Usuarios.id_usuario.in_(list({autor for autor in autores_ids if autor}) or [0])).all()
    }
    materia_color = obtener_color_materia(alumno, clase_obj.id_clase)

    return render_template(
        'Panel_Alumno/Aula/foro_detalle.html',
        foro=foro,
        clase=clase_obj,
        alumno=alumno,
        autores=autores,
        materia_color=materia_color
    )

@app.route('/alumno/examen/<int:id_examen>', methods=['GET', 'POST'])
def alumno_examen_detalle(id_examen):
    if session.get('rol') != 3:
        return redirect(url_for('login'))

    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first_or_404()
    examen = Examenes.query.get_or_404(id_examen)
    clase_obj = Clases.query.get_or_404(examen.id_clase)
    if not alumno_tiene_acceso_clase(alumno, clase_obj):
        flash('No tienes acceso a este examen.', 'danger')
        return redirect(url_for('alumno_clases'))

    entrega = EntregasExamenes.query.filter_by(id_examen=id_examen, id_alumno=alumno.id_alumno).first()

    if request.method == 'POST':
        archivo = request.files.get('archivo_respuesta')
        respuesta_texto = (request.form.get('respuesta_texto') or '').strip()
        respuestas_json = None
        archivo_ruta = entrega.archivo_ruta if entrega else None

        if examen.modalidad == 'formulario':
            respuestas_json = {}
            for pregunta in examen.preguntas:
                respuestas_json[pregunta.texto_pregunta] = request.form.get(f'pregunta_{pregunta.id_pregunta}', '').strip()
        elif respuesta_texto:
            respuestas_json = {'respuesta_texto': respuesta_texto}

        if archivo and archivo.filename:
            filename = secure_filename(archivo.filename)
            os.makedirs('static/uploads/respuestas_examenes', exist_ok=True)
            archivo_ruta = os.path.join('static/uploads/respuestas_examenes', f'examen_{id_examen}_alu_{alumno.id_alumno}_{filename}')
            archivo.save(archivo_ruta)

        if not archivo_ruta and not respuestas_json:
            flash('Debes adjuntar una respuesta antes de entregar.', 'warning')
            return redirect(url_for('alumno_examen_detalle', id_examen=id_examen))

        if entrega:
            entrega.archivo_ruta = archivo_ruta
            entrega.respuestas_json = respuestas_json
            entrega.estado = 'Entregado'
            entrega.fecha_entrega = datetime.utcnow()
        else:
            entrega = EntregasExamenes(
                id_examen=id_examen,
                id_alumno=alumno.id_alumno,
                archivo_ruta=archivo_ruta,
                respuestas_json=respuestas_json,
                estado='Entregado'
            )
            db.session.add(entrega)

        db.session.commit()
        flash('Examen entregado correctamente.', 'success')
        return redirect(url_for('alumno_examen_detalle', id_examen=id_examen))

    materia_color = obtener_color_materia(alumno, clase_obj.id_clase)
    return render_template(
        'Panel_Alumno/Aula/examen_detalle.html',
        examen=examen,
        entrega=entrega,
        clase=clase_obj,
        alumno=alumno,
        materia_color=materia_color
    )

# --- RUTA 2: DETALLE DE TAREA ---
@app.route('/alumno/tarea/<int:id_tarea>')
def ver_detalle_tarea(id_tarea):
    id_usuario_actual = session.get('user_id')
    if not id_usuario_actual:
        return redirect(url_for('login'))

    alumno = Alumnos.query.filter_by(id_usuario=id_usuario_actual).first_or_404()
    tarea = Tareas.query.get_or_404(id_tarea)
    
    # Usamos la misma función para que el color sea el mismo que en el aula
    materia_color = obtener_color_materia(alumno, tarea.id_clase)

    # Verificamos si este alumno ya entregó ESTA tarea
    entrega = EntregasTareas.query.filter_by(
        id_tarea=id_tarea, 
        id_alumno=alumno.id_alumno
    ).first()

    archivo_tarea_url = (
        url_for('static', filename=tarea.archivo_adjunto_ruta.replace('static/', ''))
        if tarea.archivo_adjunto_ruta else None
    )
    archivo_revision_url = (
        url_for('static', filename=entrega.archivo_revision_ruta.replace('static/', ''))
        if entrega and entrega.archivo_revision_ruta else None
    )
    entrega_url = (
        url_for('static', filename=entrega.archivo_ruta.replace('static/', ''))
        if entrega and entrega.archivo_ruta else None
    )

    return render_template('/Panel_Alumno/Aula/Detalle_Tarea.html', 
                           tarea=tarea, 
                           entrega=entrega,
                           archivo_tarea_url=archivo_tarea_url,
                           archivo_revision_url=archivo_revision_url,
                           entrega_url=entrega_url,
                           materia_color=materia_color,
                           alumno=alumno)

@app.route('/alumno/subir-tarea/<int:id_tarea>', methods=['POST'])
def subir_tarea(id_tarea):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    tarea = Tareas.query.get_or_404(id_tarea)
    file = request.files.get('archivo_tarea')
    if not file or file.filename == '':
        return "No se seleccionó ningún archivo", 400

    id_usuario_actual = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=id_usuario_actual).first_or_404()
    if not alumno_tiene_acceso_clase(alumno, tarea.clase):
        flash('No tienes acceso a esta tarea.', 'danger')
        return redirect(url_for('alumno_clases'))

    archivo_ruta, archivo_nombre = guardar_archivo_subido(
        file,
        'tareas_entregas',
        f'tarea_{id_tarea}_alu_{alumno.id_alumno}'
    )
    comentario_alumno = (request.form.get('comentario_alumno') or '').strip()

    entrega_existente = EntregasTareas.query.filter_by(
        id_tarea=id_tarea,
        id_alumno=alumno.id_alumno
    ).first()

    if entrega_existente:
        entrega_existente.archivo_ruta = archivo_ruta
        entrega_existente.archivo_nombre = archivo_nombre
        entrega_existente.comentario_alumno = comentario_alumno
        entrega_existente.estado = 'Entregado'
        entrega_existente.fecha_entrega = datetime.utcnow()
        entrega_existente.comentario_maestro = None
        entrega_existente.archivo_revision_ruta = None
        entrega_existente.archivo_revision_nombre = None
        entrega_existente.fecha_revision = None
    else:
        nueva_entrega = EntregasTareas(
            id_tarea=id_tarea,
            id_alumno=alumno.id_alumno,
            archivo_ruta=archivo_ruta,
            archivo_nombre=archivo_nombre,
            comentario_alumno=comentario_alumno,
            estado='Entregado',
            fecha_entrega=datetime.utcnow()
        )
        db.session.add(nueva_entrega)
    db.session.commit()

    return redirect(url_for('ver_detalle_tarea', id_tarea=id_tarea))

@app.route('/alumno/agenda')
def alumno_agenda():
    if session.get('rol') != 3: 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    if not alumno:
        return "Perfil no encontrado", 404

    clases_ids = [c.id_clase for c in alumno.seccion.grado.clases]
    tareas = Tareas.query.filter(Tareas.id_clase.in_(clases_ids)).all()
    notas_alumno = Notas.query.filter_by(id_alumno=alumno.id_alumno).all()
    tareas_entregadas_ids = [n.id_tarea for n in notas_alumno]

    return render_template('Panel_Alumno/agenda.html', 
                           alumno=alumno, 
                           tareas=tareas,
                           entregadas_ids=tareas_entregadas_ids,
                           now=datetime.utcnow())

@app.route('/alumno/notas')
def alumno_notas():
    if session.get('rol') != 3: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    if not alumno: return "Error: Perfil no encontrado", 404
    resumen_notas = construir_resumen_notas_alumno(alumno)

    return render_template('Panel_Alumno/notas.html', 
                           alumno=alumno, 
                           resumen_notas=resumen_notas)

@app.route('/alumno/horario')
def alumno_horario():
    if session.get('rol') != 3: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    if not alumno or not alumno.seccion:
        return "Error: Perfil de alumno o sección no encontrada", 404

    horario_data = construir_matriz_horario_alumno(alumno)
    
    return render_template('Panel_Alumno/horario.html', 
                           alumno=alumno, 
                           horario_data=horario_data)


# ==============================================================================
# ------------------------------ PANEL DE ADMIN --------------------------------
# ==============================================================================
@app.route('/admin')
def admin_dashboard():
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    total_alumnos = Alumnos.query.count()
    total_maestros = Maestros.query.count()
    total_asistencias = Asistencias.query.count()
    porcentaje_asistencia = round((Asistencias.query.filter_by(estado='Presente').count() / total_asistencias) * 100) if total_asistencias > 0 else 0
    alertas_notas = Notas.query.filter(Notas.calificacion < 70).count()

    grados = Grados.query.all()
    mapa_grados = {g.nombre_grado: Alumnos.query.join(Secciones).filter(Secciones.id_grado == g.id_grado).count() for g in grados}
    ultimos_usuarios = Usuarios.query.order_by(Usuarios.fecha_registro.desc()).limit(5).all()
    
    return render_template('Admin_Panel/admin_dashboard.html', 
                           total_alumnos=total_alumnos, total_maestros=total_maestros,
                           porcentaje_asistencia=porcentaje_asistencia, alertas_notas=alertas_notas,
                           mapa_grados=mapa_grados, ultimos_usuarios=ultimos_usuarios,
                           fecha_actual=datetime.now().strftime("%d/%m/%Y"))

@app.route('/admin/reporte_asistencia')
def reporte_asistencia():
    if session.get('rol') != 1:
        return redirect(url_for('login'))

    grados = Grados.query.options(
        joinedload(Grados.secciones)
        .joinedload(Secciones.alumnos)
        .joinedload(Alumnos.usuario)
    ).order_by(Grados.id_grado.asc()).all()

    todas_asistencias = Asistencias.query.order_by(Asistencias.fecha.desc()).all()
    asist_por_alumno = {}

    for asistencia in todas_asistencias:
        alumno_stats = asist_por_alumno.setdefault(asistencia.id_alumno, {
            'presentes': 0,
            'ausentes': 0,
            'excusas': 0,
            'feriados': 0,
            'registros': 0,
            'ultima_fecha': None,
            'ultimo_estado': None
        })

        estado = (asistencia.estado or '').strip()
        if estado == 'Presente':
            alumno_stats['presentes'] += 1
        elif estado == 'Ausente':
            alumno_stats['ausentes'] += 1
        elif estado == 'Excusa':
            alumno_stats['excusas'] += 1
        elif estado == 'Feriado':
            alumno_stats['feriados'] += 1

        if estado != 'Feriado':
            alumno_stats['registros'] += 1

        if not alumno_stats['ultima_fecha']:
            alumno_stats['ultima_fecha'] = asistencia.fecha
            alumno_stats['ultimo_estado'] = estado or 'Sin estado'

    resumen_general = {
        'presentes': 0,
        'ausentes': 0,
        'excusas': 0,
        'registros': 0,
        'alumnos': 0
    }
    grados_data = []

    for grado in grados:
        grado_data = {
            'id_grado': grado.id_grado,
            'nombre': grado.nombre_grado,
            'alumnos': 0,
            'presentes': 0,
            'ausentes': 0,
            'excusas': 0,
            'registros': 0,
            'porcentaje': 0,
            'secciones': []
        }

        for seccion in sorted(grado.secciones, key=lambda seccion: (seccion.nombre_seccion or '').upper()):
            seccion_data = {
                'id_seccion': seccion.id_seccion,
                'nombre': seccion.nombre_seccion,
                'alumnos': 0,
                'presentes': 0,
                'ausentes': 0,
                'excusas': 0,
                'registros': 0,
                'porcentaje': 0,
                'alumnos_data': []
            }

            for alumno in seccion.alumnos:
                stats = asist_por_alumno.get(alumno.id_alumno, {
                    'presentes': 0,
                    'ausentes': 0,
                    'excusas': 0,
                    'feriados': 0,
                    'registros': 0,
                    'ultima_fecha': None,
                    'ultimo_estado': 'Sin registros'
                })

                porcentaje_asistencia = round((stats['presentes'] / stats['registros']) * 100, 1) if stats['registros'] else 0
                porcentaje_faltas = round((stats['ausentes'] / stats['registros']) * 100, 1) if stats['registros'] else 0

                alumno_data = {
                    'id_alumno': alumno.id_alumno,
                    'nombre': f"{alumno.usuario.nombre} {alumno.usuario.apellido}" if alumno.usuario else f"Alumno #{alumno.id_alumno}",
                    'presentes': stats['presentes'],
                    'ausentes': stats['ausentes'],
                    'excusas': stats['excusas'],
                    'registros': stats['registros'],
                    'porcentaje_asistencia': porcentaje_asistencia,
                    'porcentaje_faltas': porcentaje_faltas,
                    'ultima_fecha': stats['ultima_fecha'].strftime('%d/%m/%Y') if stats['ultima_fecha'] else 'Sin registros',
                    'ultimo_estado': stats['ultimo_estado'] or 'Sin registros'
                }

                alumno.asist_presentes = alumno_data['presentes']
                alumno.asist_ausentes = alumno_data['ausentes']
                alumno.asist_excusas = alumno_data['excusas']
                alumno.asist_total = alumno_data['registros']
                alumno.asist_pct = alumno_data['porcentaje_asistencia']
                alumno.asist_faltas_pct = alumno_data['porcentaje_faltas']
                alumno.asist_ultima_fecha = alumno_data['ultima_fecha']
                alumno.asist_ultimo_estado = alumno_data['ultimo_estado']

                seccion_data['alumnos_data'].append(alumno_data)
                seccion_data['alumnos'] += 1
                seccion_data['presentes'] += stats['presentes']
                seccion_data['ausentes'] += stats['ausentes']
                seccion_data['excusas'] += stats['excusas']
                seccion_data['registros'] += stats['registros']

            seccion_data['porcentaje'] = round((seccion_data['presentes'] / seccion_data['registros']) * 100, 1) if seccion_data['registros'] else 0
            grado_data['secciones'].append(seccion_data)
            grado_data['alumnos'] += seccion_data['alumnos']
            grado_data['presentes'] += seccion_data['presentes']
            grado_data['ausentes'] += seccion_data['ausentes']
            grado_data['excusas'] += seccion_data['excusas']
            grado_data['registros'] += seccion_data['registros']

        grado_data['porcentaje'] = round((grado_data['presentes'] / grado_data['registros']) * 100, 1) if grado_data['registros'] else 0
        grados_data.append(grado_data)
        resumen_general['alumnos'] += grado_data['alumnos']
        resumen_general['presentes'] += grado_data['presentes']
        resumen_general['ausentes'] += grado_data['ausentes']
        resumen_general['excusas'] += grado_data['excusas']
        resumen_general['registros'] += grado_data['registros']

    resumen_general['porcentaje'] = round((resumen_general['presentes'] / resumen_general['registros']) * 100, 1) if resumen_general['registros'] else 0
    resumen_general['faltas'] = resumen_general['ausentes']

    return render_template(
        'Admin_Panel/reporte_asistencia.html',
        grados=grados,
        grados_data=grados_data,
        resumen=resumen_general
    )

@app.route('/admin/reporte_notas')
def reporte_notas():
    if session.get('rol') != 1:
        return redirect(url_for('login'))

    grados = Grados.query.options(
        joinedload(Grados.secciones)
        .joinedload(Secciones.alumnos)
        .joinedload(Alumnos.usuario)
    ).order_by(Grados.id_grado.asc()).all()
    periodos = Periodos.query.order_by(Periodos.id_periodo.asc()).all()

    notas = Notas.query.options(
        joinedload(Notas.tarea),
        joinedload(Notas.examen)
    ).all()

    periodos_data = [
        {
            'id_periodo': periodo.id_periodo,
            'nombre': periodo.nombre_periodo
        }
        for periodo in periodos
    ]

    mapa_periodos = {
        (periodo.nombre_periodo or '').strip().lower(): periodo.id_periodo
        for periodo in periodos
    }

    notas_por_alumno = {}
    for nota in notas:
        alumno_bucket = notas_por_alumno.setdefault(nota.id_alumno, {
            'por_periodo': {},
            'todas': []
        })

        try:
            calificacion = float(nota.calificacion)
        except (TypeError, ValueError):
            continue

        periodo_id = None
        if nota.tarea and nota.tarea.periodo:
            periodo_id = mapa_periodos.get(nota.tarea.periodo.strip().lower())
        elif nota.examen and nota.examen.periodo:
            periodo_id = mapa_periodos.get(nota.examen.periodo.strip().lower())

        alumno_bucket['todas'].append(calificacion)

        if periodo_id:
            alumno_bucket['por_periodo'].setdefault(periodo_id, []).append(calificacion)

    resumen_general = {
        'promedio_general': 0,
        'alertas': 0,
        'alumnos': 0
    }
    grados_data = []
    promedios_generales = []

    for grado in grados:
        grado_data = {
            'id_grado': grado.id_grado,
            'nombre': grado.nombre_grado,
            'promedio': 0,
            'alumnos': 0,
            'secciones': []
        }
        promedios_grado = []

        for seccion in sorted(grado.secciones, key=lambda item: (item.nombre_seccion or '').upper()):
            seccion_data = {
                'id_seccion': seccion.id_seccion,
                'nombre': seccion.nombre_seccion,
                'promedio': 0,
                'alumnos': 0,
                'alumnos_data': []
            }
            promedios_seccion = []

            alumnos_ordenados = sorted(
                seccion.alumnos,
                key=lambda item: (
                    (item.usuario.apellido if item.usuario else ''),
                    (item.usuario.nombre if item.usuario else '')
                )
            )

            for alumno in alumnos_ordenados:
                stats = notas_por_alumno.get(alumno.id_alumno, {'por_periodo': {}, 'todas': []})
                promedios_periodo = {}

                for periodo in periodos_data:
                    notas_periodo = stats['por_periodo'].get(periodo['id_periodo'], [])
                    promedios_periodo[periodo['id_periodo']] = round(
                        sum(notas_periodo) / len(notas_periodo), 1
                    ) if notas_periodo else None

                promedio_final = round(sum(stats['todas']) / len(stats['todas']), 1) if stats['todas'] else None
                estado = 'Sin notas'
                if promedio_final is not None:
                    if promedio_final < 70:
                        estado = 'Reprobado'
                        resumen_general['alertas'] += 1
                    elif promedio_final < 80:
                        estado = 'En riesgo'
                    else:
                        estado = 'Aprobado'

                    promedios_seccion.append(promedio_final)
                    promedios_grado.append(promedio_final)
                    promedios_generales.append(promedio_final)

                alumno_data = {
                    'id_alumno': alumno.id_alumno,
                    'nombre': f"{alumno.usuario.nombre} {alumno.usuario.apellido}" if alumno.usuario else f"Alumno #{alumno.id_alumno}",
                    'promedios_periodo': promedios_periodo,
                    'promedio_final': promedio_final,
                    'estado': estado
                }

                seccion_data['alumnos_data'].append(alumno_data)
                seccion_data['alumnos'] += 1
                resumen_general['alumnos'] += 1

            seccion_data['promedio'] = round(sum(promedios_seccion) / len(promedios_seccion), 1) if promedios_seccion else 0
            grado_data['secciones'].append(seccion_data)
            grado_data['alumnos'] += seccion_data['alumnos']

        grado_data['promedio'] = round(sum(promedios_grado) / len(promedios_grado), 1) if promedios_grado else 0
        grados_data.append(grado_data)

    resumen_general['promedio_general'] = round(
        sum(promedios_generales) / len(promedios_generales), 1
    ) if promedios_generales else 0

    return render_template(
        'Admin_Panel/reporte_notas.html',
        grados_data=grados_data,
        periodos_data=periodos_data,
        resumen=resumen_general
    )

def generar_nuevo_carnet():
    """Genera un carnet con formato AAAA-001 basado en el ciclo lectivo activo"""
    ciclo_activo = CiclosLectivos.query.filter_by(estado='ACTIVO').first()
    
    if ciclo_activo:
        import re
        coincidencia = re.search(r'\d{4}', ciclo_activo.nombre_ciclo)
        prefijo_ano = coincidencia.group() if coincidencia else str(datetime.now().year)
    else:
        prefijo_ano = str(datetime.now().year)
        
    prefijo = f"{prefijo_ano}-"
    ultimo_alumno = Alumnos.query.filter(Alumnos.carnet.like(f"{prefijo}%"))\
                             .order_by(Alumnos.carnet.desc()).first()
    if ultimo_alumno:
        try:
            ultimo_numero = int(ultimo_alumno.carnet.split('-')[1])
            nuevo_numero = ultimo_numero + 1
        except (IndexError, ValueError):
            nuevo_numero = 1
    else:
        nuevo_numero = 1
        
    return f"{prefijo}{nuevo_numero:03d}"

def obtener_id_ciclo_activo():
    """Busca el ID del ciclo que el administrador dejó como ACTIVO"""
    ciclo = CiclosLectivos.query.filter_by(estado='ACTIVO').first()
    return ciclo.id_cycle if ciclo else 1

def obtener_periodos_disponibles():
    periodos = Periodos.query.filter_by(id_cycle=obtener_id_ciclo_activo()).order_by(Periodos.id_periodo.asc()).all()
    if periodos:
        return periodos

    ultimo_ciclo_con_periodos = db.session.query(Periodos.id_cycle).order_by(Periodos.id_cycle.desc()).first()
    if ultimo_ciclo_con_periodos:
        return Periodos.query.filter_by(id_cycle=ultimo_ciclo_con_periodos[0]).order_by(Periodos.id_periodo.asc()).all()

    return []

@app.route('/admin/anuncios')
def vista_anuncios():
    if session.get('rol') != 1:
        return redirect(url_for('login'))
    
    lista_anuncios = Anuncios.query.order_by(Anuncios.fecha_publicacion.desc()).all()
    return render_template('Admin_Panel/gestion_anuncios.html', anuncios=lista_anuncios)

@app.route('/admin/anuncio/nuevo', methods=['POST'])
def crear_anuncio():
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    nuevo = Anuncios(
        titulo=request.form.get('titulo'),
        contenido=request.form.get('contenido'),
        dirigido_a=request.form.get('dirigido_a'),
        id_usuario_autor=session.get('user_id')
    )
    
    try:
        db.session.add(nuevo)
        db.session.commit()
        flash("Anuncio publicado con éxito", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al publicar: {str(e)}", "danger")
        
    return redirect(url_for('vista_anuncios'))

@app.route('/admin/anuncios/eliminar/<int:id>', methods=['POST'])
def eliminar_anuncio(id):
    if session.get('rol') != 1:
        return redirect(url_for('login'))
        
    anuncio = Anuncios.query.get_or_404(id)
    try:
        db.session.delete(anuncio)
        db.session.commit()
        flash("Anuncio eliminado", "warning")
    except:
        db.session.rollback()
        flash("No se pudo eliminar", "danger")
        
    return redirect(url_for('vista_anuncios'))

@app.route('/admin/nuevo/maestro')
def vista_nuevo_maestro(): 
    return render_template('Admin_Panel/usuario_nuevo.html', active_tab='maestro')

@app.route('/admin/nuevo/alumno')
def vista_nuevo_alumno():
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    carnet_sugerido = generar_nuevo_carnet()
    secciones = Secciones.query.options(joinedload(Secciones.grado)).all()
    
    return render_template('Admin_Panel/usuario_nuevo.html', 
                           active_tab='alumno', 
                           carnet=carnet_sugerido,
                           secciones=secciones)

@app.route('/admin/usuario/guardar', methods=['POST'])
def crear_usuario_logica():
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    # Creamos el usuario base
    nuevo = Usuarios(
        nombre=request.form.get('nombre'), 
        apellido=request.form.get('apellido'), 
        correo=request.form.get('correo'), 
        contrasena=generate_password_hash(request.form.get('password')), 
        id_rol=int(request.form.get('id_rol'))
    )
    db.session.add(nuevo)    
    db.session.flush()

    # Si es Maestro (Rol 2)
    if nuevo.id_rol == 2: 
        db.session.add(Maestros(
            id_usuario=nuevo.id_usuario, 
            especialidad=request.form.get('especialidad')
        ))
        
    elif nuevo.id_rol == 3: 
        db.session.add(Alumnos(
            id_usuario=nuevo.id_usuario, 
            carnet=request.form.get('carnet'),
            id_seccion=request.form.get('id_seccion')
        ))
        
    db.session.commit()
    flash("Usuario registrado correctamente")
    
    if nuevo.id_rol == 2:
        return redirect(url_for('gestion_usuarios') + '#tab-maestros')
    
    return redirect(url_for('gestion_usuarios') + '#tab-alumnos')

@app.route('/admin/gestion_usuarios')
def gestion_usuarios():
    tab_solicitada = request.args.get('tab', 'alumnos')
    
    alumnos = Alumnos.query.options(
        joinedload(Alumnos.usuario), 
        joinedload(Alumnos.seccion).joinedload(Secciones.grado)
    ).all()
    
    maestros = Maestros.query.options(
        joinedload(Maestros.usuario), 
        joinedload(Maestros.clases)
    ).all()
    
    return render_template(
        'Admin_Panel/gestion_usuarios.html', 
        alumnos=alumnos, 
        maestros=maestros, 
        vista_activa=tab_solicitada
    )

@app.route('/admin/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    usuario = Usuarios.query.get_or_404(id_usuario)
    
    if request.method == 'POST':
        usuario.nombre = request.form.get('nombre')
        usuario.apellido = request.form.get('apellido')
        usuario.correo = request.form.get('correo')
        
        if usuario.id_rol == 2 and usuario.maestro_perfil:
            usuario.maestro_perfil.especialidad = request.form.get('especialidad')
            
        elif usuario.id_rol == 3 and usuario.alumno_perfil:
            usuario.alumno_perfil.carnet = request.form.get('carnet')
            usuario.alumno_perfil.id_seccion = request.form.get('id_seccion')
            
        db.session.commit()
        flash('Usuario actualizado', 'success')
        
        # --- 🚀 CAMBIO AQUÍ: Redirección usando el parámetro 'tab' ---
        if usuario.id_rol == 2:
            return redirect(url_for('gestion_usuarios', tab='maestros'))
            
        return redirect(url_for('gestion_usuarios', tab='alumnos'))
        
    secciones = Secciones.query.all() 
        
    return render_template('Admin_Panel/editar_usuario.html', usuario=usuario, secciones=secciones)

@app.route('/admin/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    if session.get('rol') != 1: return redirect(url_for('login'))
    usuario = Usuarios.query.get_or_404(id_usuario)
    
    # 💡 Guardamos el rol antes de borrar al usuario para saber a qué pestaña volver
    rol_eliminado = usuario.id_rol
    
    try:
        # Primero borramos las tablas hijas para no romper la integridad referencial
        if usuario.id_rol == 2 and usuario.maestro_perfil:
            db.session.delete(usuario.maestro_perfil)
        elif usuario.id_rol == 3 and usuario.alumno_perfil:
            db.session.delete(usuario.alumno_perfil)
            
        # Ahora sí, borramos al usuario base
        db.session.delete(usuario)
        db.session.commit()
        flash('Registro eliminado permanentemente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('No se pudo eliminar el registro porque tiene datos vinculados', 'error')
        
    # 🚀 REDIRECCIÓN INTELIGENTE USANDO EL ROL GUARDADO
    if rol_eliminado == 2:
        return redirect(url_for('gestion_usuarios') + '#tab-maestros')
        
    return redirect(url_for('gestion_usuarios') + '#tab-alumnos')

@app.route('/admin/configuracion', methods=['GET', 'POST'])
def configuracion_academica():
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    # Capturamos la pestaña que se está visualizando (por defecto 'tab-grados')
    tab_actual = request.args.get('tab', 'tab-grados')
    
    if request.method == 'POST':
        # --- Lógica de Grados ---
        if 'guardar_grado' in request.form:
            tab_actual = 'tab-grados'
            db.session.add(Grados(nombre_grado=request.form.get('nombre_grado')))
        
        # --- Lógica de Materias ---
        elif 'guardar_clase' in request.form:
            tab_actual = 'tab-materias'
            id_ciclo_actual = obtener_id_ciclo_activo()
            
            nueva_clase = Clases(
                nombre_clase=request.form.get('nombre_clase'), 
                id_maestro=request.form.get('id_maestro') or None, 
                id_ciclo=id_ciclo_actual, # 👈 Ya no es estático
                id_grado=request.form.get('id_grado')
            )
            db.session.add(nueva_clase)
        
        # --- Lógica de Secciones ---
        elif 'guardar_seccion' in request.form:
            tab_actual = 'tab-secciones'
            nueva_seccion = Secciones(
                nombre_seccion=request.form.get('nombre_seccion'), 
                id_grado=request.form.get('id_grado')
            )
            db.session.add(nueva_seccion)

        # --- Lógica de Ciclos Lectivos ---
        elif 'guardar_ciclo' in request.form:
            tab_actual = 'tab-ciclos'
            anio = request.form.get('anio_ciclo')
            nombre_completo = f"Ciclo Lectivo {anio}"
            
            nuevo_ciclo = CiclosLectivos(
                nombre_ciclo=nombre_completo,
                fecha_inicio=None,  
                fecha_fin=None,     
                estado='INACTIVO'
            )
            db.session.add(nuevo_ciclo)
            db.session.commit()
            
            flash(f"El {nombre_completo} ha sido registrado como Inactivo.", "success")
            return redirect(url_for('configuracion_academica', tab=tab_actual))
            
        elif 'activar_ciclo' in request.form:
            tab_actual = 'tab-ciclos'
            id_ciclo = request.form.get('id_ciclo_a_activar')
            hoy = datetime.now().date()
            
            # 1. Buscamos si hay un ciclo ACTIVO actualmente
            ciclo_anterior = CiclosLectivos.query.filter_by(estado='ACTIVO').first()
            
            # Si hay uno, lo finalizamos y le ponemos la fecha de hoy como fin
            if ciclo_anterior:
                ciclo_anterior.estado = 'FINALIZADO'
                ciclo_anterior.fecha_fin = hoy
            
            # 2. Buscamos el nuevo ciclo que queremos activar
            ciclo = CiclosLectivos.query.get(id_ciclo)
            
            if ciclo:
                ciclo.estado = 'ACTIVO'
                ciclo.fecha_inicio = hoy # Se estampa la fecha de inicio automáticamente
                
                db.session.commit()
                flash(f"¡El {ciclo.nombre_ciclo} ahora es el ciclo en curso!", "success")
            else:
                flash("Error: No se pudo encontrar el ciclo para activar.", "danger")
                
            return redirect(url_for('configuracion_academica', tab=tab_actual))

        # 🔥 AGREGADO: FINALIZAR CICLO MANUALMENTE SIN ABRIR OTRO
        elif 'finalizar_ciclo' in request.form:
            tab_actual = 'tab-ciclos'
            id_ciclo = request.form.get('id_ciclo_a_finalizar')
        
            hoy = datetime.now().date()
            
            ciclo = CiclosLectivos.query.get(id_ciclo)
            
            if ciclo:
                ciclo.estado = 'FINALIZADO'
                ciclo.fecha_fin = hoy 
                
                db.session.commit()
                flash(f"El {ciclo.nombre_ciclo} ha sido finalizado con éxito.", "success")
            else:
                flash("Error: No se pudo encontrar el ciclo para finalizar.", "danger")
                
            return redirect(url_for('configuracion_academica', tab=tab_actual))

        # --- Lógica: Guardar Horario Manual ---
        elif 'id_clase' in request.form and 'id_seccion' in request.form and 'guardar_horario_manual' in request.form:
            tab_actual = 'tab-horarios'
            try:
                id_clase = int(request.form.get('id_clase'))
                id_seccion = int(request.form.get('id_seccion'))
                dias_seleccionados = request.form.getlist('dias_seleccionados')
                if not dias_seleccionados:
                    flash("⚠️ Debes seleccionar al menos un día de la semana.")
                    return redirect(url_for('configuracion_academica', tab=tab_actual))

                h_inicio = datetime.strptime(request.form.get('hora_inicio'), '%H:%M').time()
                h_fin = datetime.strptime(request.form.get('hora_fin'), '%H:%M').time()

                if h_fin <= h_inicio:
                    flash("⚠️ La hora de fin debe ser posterior a la hora de inicio.")
                    return redirect(url_for('configuracion_academica', tab=tab_actual))

                for dia in dias_seleccionados:
                    error_validacion = validar_bloque_horario(id_clase, id_seccion, dia, h_inicio, h_fin)
                    if error_validacion:
                        flash(f"⚠️ {dia}: {error_validacion}", "warning")
                        return redirect(url_for('configuracion_academica', tab=tab_actual))

                    nuevo_bloque = Horarios(
                        id_clase=id_clase,
                        id_seccion=id_seccion,
                        dia_semana=dia,
                        hora_inicio=h_inicio,
                        hora_fin=h_fin
                    )
                    db.session.add(nuevo_bloque)

                sincronizacion = sincronizar_horarios_grado_desde_seccion(id_seccion)
                if sincronizacion['ok']:
                    secciones_sync = sincronizacion.get('sincronizadas', [])
                    secciones_omitidas = sincronizacion.get('omitidas', [])

                    if secciones_sync:
                        flash(
                            f"¡Bloques guardados! Se sincronizó el horario automáticamente con las secciones: {', '.join(secciones_sync)}.",
                            "success"
                        )
                    else:
                        flash("¡Horarios guardados correctamente!", "success")

                    if secciones_omitidas:
                        flash(
                            f"No se pudo regenerar el horario de estas secciones por choques de maestros: {', '.join(secciones_omitidas)}.",
                            "warning"
                        )
                else:
                    flash("¡Horarios guardados correctamente!", "success")

            except Exception as e:
                db.session.rollback()
                flash(f"Error al procesar el horario: {str(e)}")
                return redirect(url_for('configuracion_academica', tab=tab_actual))

        # --- LÓGICA: SINCRONIZAR HORARIOS DEL GRADO DESDE UNA SECCIÓN BASE ---
        elif 'sincronizar_grado' in request.form:
            tab_actual = 'tab-horarios'
            try:
                id_origen = int(request.form.get('id_seccion_origen'))
                sincronizacion = sincronizar_horarios_grado_desde_seccion(id_origen)

                if not sincronizacion['ok']:
                    flash(sincronizacion['mensaje'], "warning")
                    return redirect(url_for('configuracion_academica', tab=tab_actual))

                secciones_sync = sincronizacion.get('sincronizadas', [])
                secciones_omitidas = sincronizacion.get('omitidas', [])

                if secciones_sync:
                    flash(
                        f"Sincronización completada. Se generó el horario para: {', '.join(secciones_sync)}.",
                        "success"
                    )
                else:
                    flash("No hay otras secciones en este grado para sincronizar.", "info")

                if secciones_omitidas:
                    flash(
                        f"Estas secciones se mantuvieron sin cambios porque no se encontró una distribución libre de choques: {', '.join(secciones_omitidas)}.",
                        "warning"
                    )

            except Exception as e:
                db.session.rollback()
                flash(f"Error en la sincronización automática: {str(e)}")
                return redirect(url_for('configuracion_academica', tab=tab_actual))

        db.session.commit()
        # Redirige conservando la pestaña tras un POST exitoso
        return redirect(url_for('configuracion_academica', tab=tab_actual))

    # --- LÓGICA PARA PETICIONES GET ---
    maestros_para_select = Maestros.query.all()
    todos_los_horarios = Horarios.query.order_by(Horarios.dia_semana, Horarios.hora_inicio).all()
    
    # Aquí pasamos la variable 'tab_activa' al HTML
    return render_template('Admin_Panel/configuracion_academica.html', 
                           grados=Grados.query.all(), 
                           clases=Clases.query.all(), 
                           secciones=Secciones.query.all(), 
                           maestros=maestros_para_select,
                           horarios=todos_los_horarios,
                           ciclos=CiclosLectivos.query.all(),
                           tab_activa=tab_actual)

#----------------------- LOGICA DE ELIMINACION -----------------------
@app.route('/admin/configuracion/eliminar_grado/<int:id_grado>', methods=['POST'])
def eliminar_grado(id_grado):
    if session.get('rol') != 1: return redirect(url_for('login'))    
    tab_actual = request.args.get('tab', 'tab-grados')
    
    grado = Grados.query.get_or_404(id_grado)
    try:
        db.session.delete(grado)
        db.session.commit()
        flash("Grado eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar: Registro en uso.", "error")
        
    return redirect(url_for('configuracion_academica', tab=tab_actual))


@app.route('/admin/configuracion/eliminar_materia/<int:id_clase>', methods=['POST'])
def eliminar_materia(id_clase):
    if session.get('rol') != 1: return redirect(url_for('login'))
    tab_actual = request.args.get('tab', 'tab-materias')
    
    materia = Clases.query.get_or_404(id_clase)
    try:
        db.session.delete(materia)
        db.session.commit()
        flash("Materia eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar la materia: tiene registros vinculados (notas o tareas).", "error")
    
    return redirect(url_for('configuracion_academica', tab=tab_actual))


@app.route('/admin/configuracion/eliminar_seccion/<int:id_seccion>', methods=['POST'])
def eliminar_seccion(id_seccion):
    if session.get('rol') != 1: return redirect(url_for('login'))
    tab_actual = request.args.get('tab', 'tab-secciones')
    
    seccion = Secciones.query.get_or_404(id_seccion)
    try:
        db.session.delete(seccion)
        db.session.commit()
        flash("Sección eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar la sección: tiene alumnos vinculados.", "error")
    
    return redirect(url_for('configuracion_academica', tab=tab_actual))


@app.route('/admin/horario/eliminar/<int:id>', methods=['POST'])
def eliminar_horario(id):
    if session.get('rol') != 1: return redirect(url_for('login'))
    tab_actual = request.args.get('tab', 'tab-horarios')
    
    horario = Horarios.query.get_or_404(id)
    try:
        db.session.delete(horario)
        db.session.commit()
        flash('Registro de horario eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al intentar eliminar el horario.', 'danger')
        
    return redirect(url_for('configuracion_academica', tab=tab_actual))
    
# ==========================================
# GESTIÓN Y EDICIÓN DE ASIGNACIONES
# ==========================================

@app.route('/maestro/grado/<int:id_grado>/gestionar_asignaciones')
def gestionar_asignaciones(id_grado):
    # 1. Validar que sea un maestro logueado
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    grado = Grados.query.get_or_404(id_grado)

    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    clases_del_grado = Clases.query.filter_by(id_grado=id_grado, id_maestro=perfil.id_maestro).all() if perfil else []
    
    # Extraemos solo los IDs de esas clases (ej: [1, 2, 5])
    ids_clases = [clase.id_clase for clase in clases_del_grado]

    # 3. Buscar las tareas y exámenes usando el id_clase
    if ids_clases:
        tareas = Tareas.query.filter(Tareas.id_clase.in_(ids_clases)).order_by(Tareas.fecha_entrega.desc()).all()
        examenes = Examenes.query.filter(Examenes.id_clase.in_(ids_clases)).order_by(Examenes.fecha_limite.desc()).all()
    else:
        # Si el grado no tiene clases aún, enviamos listas vacías
        tareas = []
        examenes = []

    return render_template('Panel_Maestro/gestionar_asignaciones.html', 
                           grado=grado, 
                           tareas=tareas, 
                           examenes=examenes,
                           periodos=obtener_periodos_disponibles())


@app.route('/maestro/tarea/borrar/<int:id_tarea>', methods=['POST'])
def borrar_tarea(id_tarea):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    id_grado = request.form.get('id_grado')
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    tarea = Tareas.query.join(Clases, Clases.id_clase == Tareas.id_clase).filter(
        Tareas.id_tarea == id_tarea,
        Clases.id_maestro == perfil.id_maestro
    ).first_or_404()

    try:
        db.session.delete(tarea)
        db.session.commit()
        flash("Tarea eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error al borrar tarea: {e}")
        flash("No se pudo eliminar la tarea.", "danger")

    return redirect(url_for('gestionar_asignaciones', id_grado=id_grado))


@app.route('/maestro/examen/borrar/<int:id_examen>', methods=['POST'])
def borrar_examen(id_examen):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    id_grado = request.form.get('id_grado')
    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    examen = Examenes.query.join(Clases, Clases.id_clase == Examenes.id_clase).filter(
        Examenes.id_examen == id_examen,
        Clases.id_maestro == perfil.id_maestro
    ).first_or_404()

    try:
        db.session.delete(examen)
        db.session.commit()
        flash("Examen eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error al borrar examen: {e}")
        flash("No se pudo eliminar el examen.", "danger")

    return redirect(url_for('gestionar_asignaciones', id_grado=id_grado))

# ==========================================
# RUTAS PARA EDITAR DESDE EL MODAL
# ==========================================

@app.route('/maestro/tarea/editar/<int:id_tarea>', methods=['POST'])
def editar_tarea(id_tarea):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    tarea = Tareas.query.join(Clases, Clases.id_clase == Tareas.id_clase).filter(
        Tareas.id_tarea == id_tarea,
        Clases.id_maestro == perfil.id_maestro
    ).first_or_404()
    clase = Clases.query.get(tarea.id_clase) # Para saber a qué grado regresar

    # Actualizamos los datos con lo que venga del modal
    tarea.titulo = request.form.get('titulo')
    tarea.descripcion = request.form.get('descripcion')
    tarea.periodo = request.form.get('periodo')
    tarea.puntos = float(request.form.get('puntos', tarea.puntos or 100))
    
    fecha_str = request.form.get('fecha_entrega')
    if fecha_str:
        # Convertimos la fecha del input datetime-local a formato de base de datos
        tarea.fecha_entrega = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
    
    db.session.commit()
    flash("Tarea actualizada correctamente.", "success")
    return redirect(url_for('gestionar_asignaciones', id_grado=clase.id_grado))


@app.route('/maestro/examen/editar/<int:id_examen>', methods=['POST'])
def editar_examen(id_examen):
    if session.get('rol') != 2:
        return redirect(url_for('login'))

    perfil = Maestros.query.filter_by(id_usuario=session.get('user_id')).first()
    examen = Examenes.query.join(Clases, Clases.id_clase == Examenes.id_clase).filter(
        Examenes.id_examen == id_examen,
        Clases.id_maestro == perfil.id_maestro
    ).first_or_404()
    clase = Clases.query.get(examen.id_clase)

    # Actualizamos los datos
    examen.titulo = request.form.get('titulo')
    examen.descripcion = request.form.get('descripcion')
    examen.modalidad = request.form.get('modalidad')
    examen.periodo = request.form.get('periodo')
    examen.puntos_maximos = float(request.form.get('puntos_maximos', examen.puntos_maximos or 100))
    
    fecha_str = request.form.get('fecha_limite')
    if fecha_str:
        examen.fecha_limite = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
        
    db.session.commit()
    flash("Examen actualizado correctamente.", "success")
    return redirect(url_for('gestionar_asignaciones', id_grado=clase.id_grado))

if __name__ == '__main__':
    app.run(debug=True)
