from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from sqlalchemy.orm import joinedload
from models import db, Usuarios, Maestros, Alumnos, Clases, Notas, Asistencias, Anuncios, Grados, Secciones, Tareas, CiclosLectivos

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

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

@app.route('/mi-cuenta')
def mi_cuenta():
    if not session.get('user_id'): return redirect(url_for('login'))
    user_id = session.get('user_id')
    usuario = Usuarios.query.get(user_id)
    perfil = Maestros.query.filter_by(id_usuario=user_id).first() if usuario.id_rol == 2 else Alumnos.query.filter_by(id_usuario=user_id).first()
    return render_template('mi_cuenta.html', usuario=usuario, perfil=perfil)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


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

@app.route('/maestro/tareas')
def historial_tareas():
    """Muestra la vista de tareas_historial.html"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    tareas = []
    if perfil:
        clases_maestro = Clases.query.filter_by(id_maestro=perfil.id_maestro).all()
        ids_clases = [c.id_clase for c in clases_maestro]
        tareas = Tareas.query.filter(Tareas.id_clase.in_(ids_clases)).all()
        
    return render_template('Panel_Maestro/tareas_historial.html', tareas=tareas)

@app.route('/maestro/tareas/crear')
def vista_nueva_tarea():
    """Muestra el formulario para crear una nueva tarea"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    return render_template('Panel_Maestro/tareas_nuevas.html')

@app.route('/maestro/tareas/nueva', methods=['POST'])
def crear_tarea():
    """Procesa el formulario cuando el maestro le da a Guardar Tarea"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    nueva_tarea = Tareas(
        id_clase=request.form.get('id_clase'),
        titulo=request.form.get('titulo'),
        fecha_entrega=datetime.strptime(request.form.get('fecha_entrega'), '%Y-%m-%dT%H:%M')
    )
    db.session.add(nueva_tarea)
    db.session.commit()
    flash("Tarea creada exitosamente", "success")
    
    return redirect(url_for('historial_tareas'))

@app.route('/maestro/notas/general')
def registrar_notas():
    """Abre el panel general de notas_subir.html"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    return render_template('Panel_Maestro/notas_subir.html')

@app.route('/maestro/grados/ver')
def ver_grados():
    """Muestra los grados asignados al maestro (grados.html)"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    return render_template('Panel_Maestro/grados.html')

@app.route('/maestro/grado/<int:id_grado>')
def gestionar_grado(id_grado):
    """Muestra los alumnos específicos de un grado (maestro_gestion_grado.html)"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    alumnos = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()
    grado = Grados.query.get(id_grado)
    return render_template('Panel_Maestro/maestro_gestion_grado.html', grado=grado, alumnos=alumnos)

@app.route('/maestro/reportes/enviar')
def enviar_reportes():
    """Muestra la vista de reportes_enviar.html"""
    if session.get('rol') != 2: return redirect(url_for('login'))
    return render_template('Panel_Maestro/reportes_enviar.html')

@app.route('/maestro/asistencia/control')
def control_asistencia():
    if session.get('rol') != 2: return redirect(url_for('login'))
    return "Módulo de Control de Asistencia. (Aún no tienes el HTML creado para esto en tu carpeta)"

@app.route('/maestro/datos/exportar')
def exportar_datos():
    if session.get('rol') != 2: return redirect(url_for('login'))
    return "Módulo para Exportar Datos. (Aún no tienes el HTML creado para esto en tu carpeta)"


# ==============================================================================
# ------------------------------ PANEL DE ALUMNO -------------------------------
# ==============================================================================
@app.route('/alumno')
def alumno_dashboard():
    if session.get('rol') != 3: return redirect(url_for('login'))
    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first()
    notas = Notas.query.filter_by(id_alumno=alumno.id_alumno).all() if alumno else []
    asistencias = Asistencias.query.filter_by(id_alumno=alumno.id_alumno).all() if alumno else []
    anuncios = Anuncios.query.filter(Anuncios.dirigido_a.in_(['Todos', 'Alumnos'])).all()
    return render_template('Panel_Alumno/alumno_dash.html', notas=notas, asistencias=asistencias, anuncios=anuncios)


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

@app.route('/admin/anuncio/nuevo', methods=['POST'])
def crear_anuncio():
    if session.get('rol') != 1: return redirect(url_for('login'))
    anuncio = Anuncios(titulo=request.form.get('titulo'), contenido=request.form.get('contenido'), dirigido_a=request.form.get('dirigido_a'), id_usuario_autor=session.get('user_id'))
    db.session.add(anuncio)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/nuevo/maestro')
def vista_nuevo_maestro(): 
    return render_template('Admin_Panel/usuario_nuevo.html', active_tab='maestro')

@app.route('/admin/nuevo/alumno')
def vista_nuevo_alumno():
    carnet_sugerido = generar_nuevo_carnet()
    secciones = Secciones.query.options(joinedload(Secciones.grado)).all()
    
    return render_template('Admin_Panel/usuario_nuevo.html', 
                           active_tab='alumno', 
                           carnet=carnet_sugerido,
                           secciones=secciones)



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

def generar_nuevo_carnet():
    año_actual = datetime.now().year
    prefijo = f"{año_actual}-"
    
    ultimo_alumno = Alumnos.query.filter(Alumnos.carnet.like(f"{prefijo}%"))\
                            .order_by(Alumnos.carnet.desc()).first()
    
    if ultimo_alumno:
        ultimo_numero = int(ultimo_alumno.carnet.split('-')[1])
        nuevo_numero = ultimo_numero + 1
    else:
        nuevo_numero = 1
        
    return f"{prefijo}{nuevo_numero:03d}"

# ---------------- GESTIÓN CENTRALIZADA DE USUARIOS (LEER Y ELIMINAR) ----------------

@app.route('/admin/gestion_usuarios')
def gestion_usuarios():

    alumnos = Alumnos.query.options(
        joinedload(Alumnos.usuario),
        joinedload(Alumnos.seccion).joinedload(Secciones.grado)
    ).all()

    maestros = Maestros.query.options(
        joinedload(Maestros.usuario),
        joinedload(Maestros.clases)
    ).all()
    
    return render_template('Admin_Panel/gestion_usuarios.html', 
                           alumnos=alumnos, 
                           maestros=maestros,
                           vista_activa='alumnos')

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
        print(f"Error al eliminar: {e}")
        flash('No se pudo eliminar el registro porque tiene datos vinculados (notas, clases, etc.)', 'error')
        
    return redirect(url_for('gestion_usuarios'))


# ---------------- CONFIGURACION ACADEMICA ----------------

@app.route('/admin/configuracion', methods=['GET', 'POST'])
def configuracion_academica():
    if session.get('rol') != 1: return redirect(url_for('login'))

    if request.method == 'POST':
        # Guardar Grado
        if 'guardar_grado' in request.form:
            db.session.add(Grados(nombre_grado=request.form.get('nombre_grado')))
        
        # Guardar Clase/Materia
        elif 'guardar_clase' in request.form:
            nueva_clase = Clases(
                nombre_clase=request.form.get('nombre_clase'),
                id_maestro=request.form.get('id_maestro') or None, 
                id_ciclo=1, 
                id_grado=request.form.get('id_grado')
            )
            db.session.add(nueva_clase)
        
        elif 'guardar_seccion' in request.form:
            nueva_seccion = Secciones(
                nombre_seccion=request.form.get('nombre_seccion'),
                id_grado=request.form.get('id_grado')
            )
            db.session.add(nueva_seccion)
        
        db.session.commit()
        flash("Registro guardado correctamente")
        return redirect(url_for('configuracion_academica'))
    
    maestros_para_select = Maestros.query.all() 

    return render_template('Admin_Panel/configuracion_academica.html', 
                            grados=Grados.query.all(), 
                            clases=Clases.query.all(),
                            secciones=Secciones.query.all(),
                            maestros=maestros_para_select)

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
        flash("No se puede eliminar: Este grado ya tiene secciones o alumnos asignados.", "error")
        
    return redirect(url_for('configuracion_academica'))


@app.route('/admin/configuracion/eliminar_materia/<int:id_clase>', methods=['POST'])
def eliminar_materia(id_clase):
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    materia = Clases.query.get_or_404(id_clase)
    try:
        db.session.delete(materia)
        db.session.commit()
        flash("Materia eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar: Esta materia ya está en uso.", "error")
        
    return redirect(url_for('configuracion_academica'))

@app.route('/admin/configuracion/eliminar_seccion/<int:id_seccion>', methods=['POST'])
def eliminar_seccion(id_seccion):
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    seccion = Secciones.query.get_or_404(id_seccion)
    try:
        db.session.delete(seccion)
        db.session.commit()
        flash("Sección eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar: Esta sección tiene alumnos inscritos.", "error")
        
    return redirect(url_for('configuracion_academica'))


if __name__ == '__main__':
    app.run(debug=True)