from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from sqlalchemy.orm import joinedload
import os
from werkzeug.utils import secure_filename
from models import db, Usuarios, Maestros, Alumnos, Clases, Notas, Asistencias, Anuncios, Grados, Secciones, Tareas, CiclosLectivos, EntregasTareas, Examenes, PreguntasExamen, OpcionesPregunta, EntregasExamenes


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

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
    if not session.get('user_id'): return redirect(url_for('login'))
    user_id = session.get('user_id')
    usuario = Usuarios.query.get(user_id)
    perfil = Maestros.query.filter_by(id_usuario=user_id).first() if usuario.id_rol == 2 else Alumnos.query.filter_by(id_usuario=user_id).first()
    return render_template('mi_cuenta.html', usuario=usuario, perfil=perfil)

@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    if not session.get('user_id'): 
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    rol = session.get('rol')
    usuario = Usuarios.query.get(user_id)

    # Cargar perfil específico según el rol para que sea funcional
    perfil = None
    if rol == 2: # Maestro
        perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    elif rol == 3: # Alumno
        perfil = Alumnos.query.filter_by(id_usuario=user_id).first()

    if request.method == 'POST':
        accion = request.form.get('accion')

        # --- ACCIÓN 1: CAMBIO DE CONTRASEÑA ---
        if accion == 'cambiar_pass':
            pass_actual = request.form.get('pass_actual')
            pass_nueva = request.form.get('pass_nueva')
            confirm_pass = request.form.get('confirm_pass')

            if not check_password_hash(usuario.contrasena, pass_actual):
                flash("La contraseña actual es incorrecta.", "error")
            elif pass_nueva != confirm_pass:
                flash("Las contraseñas no coinciden.", "error")
            elif len(pass_nueva) < 8:
                flash("Debe tener al menos 8 caracteres.", "error")
            else:
                usuario.contrasena = generate_password_hash(pass_nueva)
                db.session.commit()
                flash("Contraseña actualizada con éxito.", "success")

        # --- ACCIÓN 2: ACTUALIZAR DATOS DE PERFIL (PERSONALIDAD) ---
        elif accion == 'actualizar_perfil':
            usuario.correo = request.form.get('correo')
            
            # Si es maestro, permitir cambiar especialidad
            if rol == 2 and perfil:
                perfil.especialidad = request.form.get('especialidad')
            
            db.session.commit()
            flash("Información de perfil actualizada.", "success")

        # --- ACCIÓN 3: PREFERENCIAS DE INTERFAZ ---
        elif accion == 'guardar_interfaz':
            # Aquí podrías guardar el modo oscuro en la BD si añades la columna a Usuarios
            flash("Preferencias visuales aplicadas.", "success")
            
        return redirect(url_for('ajustes'))

    return render_template('ajustes.html', usuario=usuario, perfil=perfil, rol=rol)


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
    anuncios = Anuncios.query.filter(Anuncios.dirigido_a.in_(['Todos', 'Maestros'])).all()
    
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
    
    return render_template('Panel_Maestro/tareas_nuevas.html', clases=clases, id_grado=id_grado, grado=grado)

@app.route('/maestro/tareas/nueva/<int:id_grado>', methods=['POST'])
def crear_tarea(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    try:
        nueva_tarea = Tareas(
            id_clase=request.form.get('id_clase'),
            titulo=request.form.get('titulo'),
            descripcion=request.form.get('descripcion'),
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
            for key, value in request.form.items():
                if key.startswith('nota_') and value.strip() != '':
                    user_id_alumno = int(key.split('_')[1])
                    alumno_db = Alumnos.query.filter_by(id_usuario=user_id_alumno).first()
                    
                    if alumno_db:
                        nota_existente = Notas.query.filter_by(id_alumno=alumno_db.id_alumno, id_tarea=id_tarea).first()
                        
                        if nota_existente:
                            nota_existente.calificacion = float(value)
                            nota_existente.id_maestro_autor = perfil.id_maestro
                            nota_existente.fecha_modificacion = datetime.utcnow()
                        else:
                            nueva_nota = Notas(
                                id_tarea=id_tarea,
                                id_alumno=alumno_db.id_alumno,
                                calificacion=float(value),
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
            archivo_url = entrega_registro.archivo_ruta if (entrega_registro and entrega_registro.archivo_ruta) else '#'
            
            entregas.append({
                'alumno': usuario_al,
                'estado': estado_entrega,
                'archivo_url': archivo_url,
                'nota': nota_registro.calificacion if nota_registro else ''
            })
            
        tareas_para_html.append({
            'id_tarea': tarea.id_tarea,
            'titulo': tarea.titulo,
            'descripcion': tarea.descripcion, 
            'fecha_entrega': tarea.fecha_entrega.strftime('%d/%m/%Y %H:%M') if tarea.fecha_entrega else 'Sin fecha',
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
                        if nota_existente:
                            nota_existente.calificacion = val_nota
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
    return render_template('Panel_Maestro/nuevo_examen.html', id_grado=id_grado, grado=grado)

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

    return render_template('Panel_Maestro/examen_archivo.html', id_grado=id_grado, grado=grado, clases=clases)

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

    return render_template('Panel_Maestro/examen_instrucciones.html', id_grado=id_grado, grado=grado, clases=clases)

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

    return render_template('Panel_Maestro/examen_formulario.html', id_grado=id_grado, grado=grado, clases=clases)
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
    
    grado = Grados.query.get_or_404(id_grado)
    
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
            
    return render_template('Panel_Maestro/asistencia.html', grado=grado, alumnos=alumnos_data)

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
    
    # 1. Obtenemos el perfil del alumno
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    if not alumno:
        return "Perfil de alumno no encontrado", 404

    # 2. Obtener Anuncios (Dirigidos a Alumnos o Todos)
    anuncios = Anuncios.query.filter(Anuncios.dirigido_a.in_(['Todos', 'Alumnos']))\
                             .order_by(Anuncios.fecha_publicacion.desc()).all()

    # 3. Obtener Clases del Alumno (Basadas en su Grado)
    # Navegamos: Alumno -> Sección -> Grado -> Clases
    clases_alumno = Clases.query.filter_by(id_grado=alumno.seccion.id_grado).all()
    ids_clases = [c.id_clase for c in clases_alumno]

    # 4. Tareas Pendientes
    # Usamos datetime.utcnow() para comparar con la fecha de entrega
    tareas_proximas = Tareas.query.filter(
        Tareas.id_clase.in_(ids_clases),
        Tareas.fecha_entrega >= datetime.utcnow()
    ).order_by(Tareas.fecha_entrega.asc()).limit(3).all()

    # 5. Cálculo de Asistencia Real
    asistencias = Asistencias.query.filter_by(id_alumno=alumno.id_alumno).all()
    total_a = len(asistencias)
    presentes = len([a for a in asistencias if a.estado == 'Presente'])
    porcentaje_asistencia = round((presentes / total_a * 100)) if total_a > 0 else 0

    # 6. Rendimiento (Promedio de Notas)
    notas_alumno = Notas.query.filter_by(id_alumno=alumno.id_alumno).all()
    if notas_alumno:
        promedio = sum(float(n.calificacion) for n in notas_alumno) / len(notas_alumno)
    else:
        promedio = 0

    return render_template('Panel_Alumno/alumno_dash.html', 
                           alumno=alumno,
                           anuncios=anuncios,
                           tareas=tareas_proximas,
                           asistencia_val=porcentaje_asistencia,
                           promedio_val=round(promedio, 1),
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

# --- RUTA 1: VISTA DEL AULA ---
@app.route('/alumno/aula/<int:id_clase>')
def alumno_aula(id_clase):
    id_usuario_actual = session.get('user_id')
    if not id_usuario_actual:
        return redirect(url_for('login'))

    # Obtenemos objetos base
    alumno = Alumnos.query.filter_by(id_usuario=id_usuario_actual).first_or_404()
    clase_obj = Clases.query.get_or_404(id_clase)
    
    # Color consistente
    materia_color = obtener_color_materia(alumno, id_clase)

    # Tareas y validación de entregas
    tareas_clase = Tareas.query.filter_by(id_clase=id_clase).order_by(Tareas.fecha_entrega.asc()).all()
    entregas = EntregasTareas.query.filter_by(id_alumno=alumno.id_alumno).all()
    entregadas_ids = [e.id_tarea for e in entregas]

    return render_template('/Panel_Alumno/Aula/Aula.html', 
                           clase=clase_obj, 
                           tareas=tareas_clase, 
                           entregadas_ids=entregadas_ids,
                           alumno=alumno,
                           materia_color=materia_color)

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

    return render_template('/Panel_Alumno/Aula/Detalle_Tarea.html', 
                           tarea=tarea, 
                           entrega=entrega,
                           materia_color=materia_color,
                           alumno=alumno)

@app.route('/alumno/subir-tarea/<int:id_tarea>', methods=['POST'])
def subir_tarea(id_tarea):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('archivo_tarea')
    if not file or file.filename == '':
        return "No se seleccionó ningún archivo", 400

    id_usuario_actual = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=id_usuario_actual).first_or_404()
    filename = secure_filename(file.filename)
    nombre_final = f"tarea_{id_tarea}_alu_{alumno.id_alumno}_{filename}"
    ruta_carpeta = os.path.join(app.root_path, 'static', 'uploads', 'tareas')
    
    if not os.path.exists(ruta_carpeta):
        os.makedirs(ruta_carpeta)
        
    file.save(os.path.join(ruta_carpeta, nombre_final))

    nueva_entrega = EntregasTareas(
        id_tarea=id_tarea,
        id_alumno=alumno.id_alumno,
        archivo_ruta=nombre_final,
        estado='Entregado'
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
    notas = Notas.query.filter_by(id_alumno=alumno.id_alumno).all()

    notas_por_materia = {}
    for nota in notas:
        nombre_clase = nota.tarea.clase.nombre_clase
        if nombre_clase not in notas_por_materia:
            notas_por_materia[nombre_clase] = []
        notas_por_materia[nombre_clase].append(nota)

    return render_template('Panel_Alumno/notas.html', 
                           alumno=alumno, 
                           notas_agrupadas=notas_por_materia)

import random

@app.route('/alumno/horario')
def alumno_horario():
    if session.get('rol') != 3: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    alumno = Alumnos.query.filter_by(id_usuario=user_id).first()
    clases = Clases.query.filter_by(id_grado=alumno.seccion.id_grado).all()
    
    # Colores predefinidos para la interfaz
    colores_ui = ['#4361ee', '#3f37c9', '#4895ef', '#4cc9f0', '#7209b7']
    
    return render_template('Panel_Alumno/horario.html', 
                           alumno=alumno, 
                           clases=clases,
                           colores=colores_ui)


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
def generar_nuevo_carnet():
    """Genera un carnet con formato AAAA-001 basado en el año actual"""
    año_actual = datetime.now().year
    prefijo = f"{año_actual}-"
    
    # Buscamos el último carnet registrado con el prefijo del año actual
    ultimo_alumno = Alumnos.query.filter(Alumnos.carnet.like(f"{prefijo}%"))\
                             .order_by(Alumnos.carnet.desc()).first()
    
    if ultimo_alumno:
        try:
            # Extraemos el número correlativo y sumamos 1
            ultimo_numero = int(ultimo_alumno.carnet.split('-')[1])
            nuevo_numero = ultimo_numero + 1
        except (IndexError, ValueError):
            nuevo_numero = 1
    else:
        nuevo_numero = 1
        
    return f"{prefijo}{nuevo_numero:03d}"


@app.route('/admin/usuario/guardar', methods=['POST'])
def crear_usuario_logica():
    if session.get('rol') != 1: return redirect(url_for('login'))
    nuevo = Usuarios(nombre=request.form.get('nombre'), apellido=request.form.get('apellido'), correo=request.form.get('correo'), contrasena=generate_password_hash(request.form.get('password')), id_rol=int(request.form.get('id_rol')))
    db.session.add(nuevo)
    db.session.commit()

    if nuevo.id_rol == 2: db.session.add(Maestros(id_usuario=nuevo.id_usuario, especialidad=request.form.get('especialidad')))
    elif nuevo.id_rol == 3: db.session.add(Alumnos(id_usuario=nuevo.id_usuario, carnet=request.form.get('carnet')))
        
    db.session.commit()
    flash("Usuario registrado correctamente")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/gestion_usuarios')
def gestion_usuarios():
    alumnos = Alumnos.query.options(joinedload(Alumnos.usuario), joinedload(Alumnos.seccion).joinedload(Secciones.grado)).all()
    maestros = Maestros.query.options(joinedload(Maestros.usuario), joinedload(Maestros.clases)).all()
    return render_template('Admin_Panel/gestion_usuarios.html', alumnos=alumnos, maestros=maestros, vista_activa='alumnos')

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
        db.session.commit()
        flash('Usuario actualizado', 'success')
        return redirect(url_for('gestion_usuarios'))
    return render_template('Admin_Panel/editar_usuario.html', usuario=usuario)

@app.route('/admin/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    if session.get('rol') != 1: return redirect(url_for('login'))
    usuario = Usuarios.query.get_or_404(id_usuario)
    try:
        if usuario.id_rol == 2 and usuario.maestro_perfil:
            db.session.delete(usuario.maestro_perfil)
        elif usuario.id_rol == 3 and usuario.alumno_perfil:
            db.session.delete(usuario.alumno_perfil)
        db.session.delete(usuario)
        db.session.commit()
        flash('Registro eliminado permanentemente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('No se pudo eliminar el registro porque tiene datos vinculados', 'error')
    return redirect(url_for('gestion_usuarios'))


@app.route('/admin/configuracion', methods=['GET', 'POST'])
def configuracion_academica():
    if session.get('rol') != 1: return redirect(url_for('login'))
    if request.method == 'POST':
        if 'guardar_grado' in request.form:
            db.session.add(Grados(nombre_grado=request.form.get('nombre_grado')))
        elif 'guardar_clase' in request.form:
            nueva_clase = Clases(nombre_clase=request.form.get('nombre_clase'), id_maestro=request.form.get('id_maestro') or None, id_ciclo=1, id_grado=request.form.get('id_grado'))
            db.session.add(nueva_clase)
        elif 'guardar_seccion' in request.form:
            nueva_seccion = Secciones(nombre_seccion=request.form.get('nombre_seccion'), id_grado=request.form.get('id_grado'))
            db.session.add(nueva_seccion)
        db.session.commit()
        flash("Registro guardado correctamente")
        return redirect(url_for('configuracion_academica'))
    maestros_para_select = Maestros.query.all() 
    return render_template('Admin_Panel/configuracion_academica.html', grados=Grados.query.all(), clases=Clases.query.all(), secciones=Secciones.query.all(), maestros=maestros_para_select)

@app.route('/admin/configuracion/eliminar_grado/<int:id_grado>', methods=['POST'])
def eliminar_grado(id_grado):
    if session.get('rol') != 1: return redirect(url_for('login'))
    grado = Grados.query.get_or_404(id_grado)
    try:
        db.session.delete(grado)
        db.session.commit()
        flash("Grado eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar: Registro en uso.", "error")
    return redirect(url_for('configuracion_academica'))

@app.route('/admin/configuracion/eliminar_materia/<int:id_clase>', methods=['POST'])
def eliminar_materia(id_clase):
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    materia = Clases.query.get_or_404(id_clase)
    try:
        db.session.delete(materia)
        db.session.commit()
        flash("Materia eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        # Esto sucede si la materia ya tiene notas o tareas vinculadas
        flash("No se puede eliminar la materia: tiene registros vinculados (notas o tareas).", "error")
    
    return redirect(url_for('configuracion_academica'))

@app.route('/admin/configuracion/eliminar_seccion/<int:id_seccion>', methods=['POST'])
def eliminar_seccion(id_seccion):
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    seccion = Secciones.query.get_or_404(id_seccion)
    try:
        db.session.delete(seccion)
        db.session.commit()
        flash("Sección eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar la sección: tiene alumnos vinculados.", "error")
    
    return redirect(url_for('configuracion_academica'))

if __name__ == '__main__':
    app.run(debug=True)