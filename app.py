from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, Usuarios, Maestros, Alumnos, Clases, Notas, Asistencias, Anuncios, Grados, Secciones, Tareas, CiclosLectivos

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# ---------------- RUTA RAÍZ ----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------------- LOGIN Y SEGURIDAD ----------------
# ---------------- LOGIN Y SEGURIDAD ----------------
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
            
            # NUEVO: Generar iniciales (primera letra del nombre y apellido)
            session['iniciales'] = f"{user.nombre[0]}{user.apellido[0]}".upper()
            
            # Asignar nombre del rol y redirigir
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
    if not session.get('user_id'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    usuario = Usuarios.query.get(user_id)
    
    # Buscamos el perfil específico dependiendo del rol
    perfil = None
    if usuario.id_rol == 2: # Maestro
        perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    elif usuario.id_rol == 3: # Alumno
        perfil = Alumnos.query.filter_by(id_usuario=user_id).first()
    
    return render_template('mi_cuenta.html', usuario=usuario, perfil=perfil)

# ---------------- DASHBOARDS Y ANUNCIOS ----------------
from datetime import datetime # Asegúrate de importar esto al inicio

@app.route('/admin')
def admin_dashboard():
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    # 1. Totales
    total_alumnos = Alumnos.query.count()
    total_maestros = Maestros.query.count()
    
    # 2. Asistencia
    total_asistencias = Asistencias.query.count()
    porcentaje_asistencia = 0
    if total_asistencias > 0:
        presentes = Asistencias.query.filter_by(estado='Presente').count()
        porcentaje_asistencia = round((presentes / total_asistencias) * 100)

    # NUEVO: 3. Alertas de Notas (Contamos notas menores a 70 o la calificación de pase)
    alertas_notas = Notas.query.filter(Notas.calificacion < 70).count()

    # 4. MAPA DE GRADOS (Clave para la gráfica)
    grados = Grados.query.all()
    mapa_grados = {}
    for g in grados:
        conteo = Alumnos.query.join(Secciones).filter(Secciones.id_grado == g.id_grado).count()
        mapa_grados[g.nombre_grado] = conteo

    # 5. Actividad y Otros
    ultimos_usuarios = Usuarios.query.order_by(Usuarios.fecha_registro.desc()).limit(5).all()
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    return render_template('Admin_Panel/admin_dashboard.html', 
                           total_alumnos=total_alumnos,
                           total_maestros=total_maestros,
                           porcentaje_asistencia=porcentaje_asistencia,
                           alertas_notas=alertas_notas, # Pasamos las alertas a la vista
                           mapa_grados=mapa_grados, 
                           ultimos_usuarios=ultimos_usuarios,
                           fecha_actual=fecha_actual)

# En app.py, busca esta función y actualízala así:
@app.route('/maestro')
def maestro_dashboard():
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    # 1. Obtenemos el objeto del usuario completo
    maestro_usuario = Usuarios.query.get(user_id) 
    
    # 2. Obtenemos el perfil de maestro para filtrar sus clases
    perfil = Maestros.query.filter_by(id_usuario=user_id).first()
    
    # 3. Consultas para los datos del dashboard
    clases = Clases.query.filter_by(id_maestro=perfil.id_maestro).all()
    anuncios = Anuncios.query.filter(Anuncios.dirigido_a.in_(['Todos', 'Maestros'])).all()
    
    # 4. PASAMOS EL OBJETO 'maestro_usuario' al template como 'maestro'
    return render_template('Panel_Maestro/maestro_dash.html', 
                           maestro=maestro_usuario, 
                           clases=clases, 
                           anuncios=anuncios)

@app.route('/alumno')
def alumno_dashboard():
    if session.get('rol') != 3: return redirect(url_for('login'))
    alumno = Alumnos.query.filter_by(id_usuario=session.get('user_id')).first()
    notas = Notas.query.filter_by(id_alumno=alumno.id_alumno).all()
    asistencias = Asistencias.query.filter_by(id_alumno=alumno.id_alumno).all()
    anuncios = Anuncios.query.filter(Anuncios.dirigido_a.in_(['Todos', 'Alumnos'])).all()
    return render_template('Panel_Alumno/alumno_dash.html', notas=notas, asistencias=asistencias, anuncios=anuncios)

# ---------------- GESTIÓN ACADÉMICA (LÓGICA MAESTRO) ----------------
@app.route('/maestro/grado/<int:id_grado>')
def gestionar_grado(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    secciones = Secciones.query.filter_by(id_grado=id_grado).all()
    ids_secciones = [s.id_seccion for s in secciones]
    alumnos = Usuarios.query.join(Alumnos).filter(Alumnos.id_seccion.in_(ids_secciones)).all()
    return render_template('Panel_Maestro/maestro_gestion_grado.html', grado=Grados.query.get(id_grado), alumnos=alumnos)

@app.route('/maestro/tareas/nueva', methods=['POST'])
def crear_tarea():
    if session.get('rol') != 2: return redirect(url_for('login'))
    nueva_tarea = Tareas(
        id_clase=request.form.get('id_clase'),
        titulo=request.form.get('titulo'),
        fecha_entrega=datetime.strptime(request.form.get('fecha_entrega'), '%Y-%m-%dT%H:%M')
    )
    db.session.add(nueva_tarea)
    db.session.commit()
    return redirect(url_for('historial_tareas'))

@app.route('/maestro/nota/registrar', methods=['POST'])
def registrar_nota():
    if session.get('rol') != 2: return redirect(url_for('login'))
    nota = Notas(
        id_tarea=request.form.get('id_tarea'),
        id_alumno=request.form.get('id_alumno'),
        calificacion=request.form.get('calificacion'),
        id_maestro_autor=session.get('user_id'), # Auditoría
        fecha_modificacion=datetime.utcnow()     # Auditoría
    )
    db.session.add(nota)
    db.session.commit()
    return redirect(url_for('maestro_dashboard'))

@app.route('/maestro/asistencia/registrar', methods=['POST'])
def registrar_asistencia():
    if session.get('rol') != 2: return redirect(url_for('login'))
    asistencia = Asistencias(
        id_clase=request.form.get('id_clase'),
        id_alumno=request.form.get('id_alumno'),
        estado=request.form.get('estado'),
        fecha=datetime.utcnow().date()
    )
    db.session.add(asistencia)
    db.session.commit()
    return redirect(url_for('maestro_dashboard'))

# ---------------- GESTIÓN DE ANUNCIOS (ADMIN) ----------------
@app.route('/admin/anuncio/nuevo', methods=['POST'])
def crear_anuncio():
    if session.get('rol') != 1: return redirect(url_for('login'))
    anuncio = Anuncios(
        titulo=request.form.get('titulo'),
        contenido=request.form.get('contenido'),
        dirigido_a=request.form.get('dirigido_a'),
        id_usuario_autor=session.get('user_id')
    )
    db.session.add(anuncio)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/nuevo/maestro')
def vista_nuevo_maestro():
    return render_template('Admin_Panel/usuario_nuevo.html', rol_nombre="Maestro", id_rol=2)

@app.route('/admin/nuevo/alumno')
def vista_nuevo_alumno():
    return render_template('Admin_Panel/usuario_nuevo.html', rol_nombre="Alumno", id_rol=3)

@app.route('/admin/usuario/guardar', methods=['POST'])
def crear_usuario_logica():
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    # 1. Guardar el usuario base
    nuevo = Usuarios(
        nombre=request.form.get('nombre'),
        apellido=request.form.get('apellido'),
        correo=request.form.get('correo'),
        contrasena=generate_password_hash(request.form.get('password')),
        id_rol=int(request.form.get('id_rol'))
    )
    db.session.add(nuevo)
    db.session.commit()

    # 2. Guardar el perfil específico
    if nuevo.id_rol == 2: # Maestro
        perfil = Maestros(id_usuario=nuevo.id_usuario, especialidad=request.form.get('especialidad'))
        db.session.add(perfil)
    elif nuevo.id_rol == 3: # Alumno
        perfil = Alumnos(id_usuario=nuevo.id_usuario, carnet=request.form.get('carnet'))
        db.session.add(perfil)
        
    db.session.commit()
    flash("Usuario registrado correctamente")
    return redirect(url_for('admin_dashboard'))

# ---------------- GESTIÓN CENTRALIZADA DE USUARIOS (LEER Y ELIMINAR) ----------------

@app.route('/admin/gestion_usuarios')
def gestion_usuarios():
    # Obtenemos ambos listados para que las pestañas funcionen sin recargar
    alumnos = Alumnos.query.join(Usuarios).all()
    maestros = Maestros.query.join(Usuarios).all()
    
    return render_template('Admin_Panel/gestion_usuarios.html', 
                           alumnos=alumnos, 
                           maestros=maestros)

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
    usuario = Usuarios.query.get_or_404(id_usuario)
    rol_vista = 'maestros' if usuario.id_rol == 2 else 'alumnos'
    
    try:
        # Al borrar el usuario, se deberían borrar los perfiles si pusiste CASCADE, 
        # si no, Flask-SQLAlchemy lo maneja por las relaciones.
        db.session.delete(usuario)
        db.session.commit()
        flash('Registro eliminado permanentemente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el registro', 'error')
        
    return redirect(url_for('gestion_usuarios', vista=rol_vista))

@app.route('/admin/configuracion', methods=['GET', 'POST'])
def configuracion_academica():
    if request.method == 'POST':
        if 'guardar_grado' in request.form:
            nuevo_grado = Grados(nombre_grado=request.form.get('nombre_grado'))
            db.session.add(nuevo_grado)
            db.session.commit()
        elif 'guardar_clase' in request.form:
            nueva_clase = Clases(nombre_clase=request.form.get('nombre_clase'))
            db.session.add(nueva_clase)
            db.session.commit()
        return redirect(url_for('configuracion_academica'))

    grados = Grados.query.all()
    clases = Clases.query.all()
    
    # CORRECCIÓN: Nombre del template actualizado para que coincida con tu archivo
    return render_template('Admin_Panel/configuracion_academica.html', grados=grados, clases=clases)

if __name__ == '__main__':
    app.run(debug=True)