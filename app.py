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
            
            if user.id_rol == 1: return redirect(url_for('admin_dashboard'))
            if user.id_rol == 2: return redirect(url_for('maestro_dashboard'))
            return redirect(url_for('alumno_dashboard'))
        flash("Credenciales incorrectas.")
    return render_template('login.html')

# ---------------- DASHBOARDS Y ANUNCIOS ----------------
from datetime import datetime # Asegúrate de importar esto al inicio

@app.route('/admin')
def admin_dashboard():
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    # 1. Obtenemos los totales (asegúrate de importar los modelos Alumno y Maestro)
    total_alumnos = Alumnos.query.count()
    total_maestros = Maestros.query.count()
    
    # 2. Obtenemos la fecha actual
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    # 3. Obtenemos los anuncios
    anuncios = Anuncios.query.order_by(Anuncios.fecha_publicacion.desc()).all()
    
    # 4. PASAMOS TODO AL TEMPLATE
    return render_template('Admin_Panel/admin_dashboard.html', 
                           anuncios=anuncios,
                           total_alumnos=total_alumnos,
                           total_maestros=total_maestros,
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

@app.route('/admin/usuarios/<vista>')
def gestion_usuarios(vista):
    if session.get('rol') != 1: return redirect(url_for('login'))
    
    # .all() traerá los objetos con sus relaciones si están configuradas en models.py
    todos_alumnos = Alumnos.query.all() 
    todos_maestros = Maestros.query.all()
    
    return render_template('Admin_Panel/gestion_usuarios.html', 
                           alumnos=todos_alumnos, 
                           maestros=todos_maestros,
                           vista_activa=vista)

@app.route('/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    if session.get('rol') != 1: 
        return redirect(url_for('login'))
    
    usuario = Usuarios.query.get_or_404(id_usuario)
    # Guardamos el rol antes de borrarlo para saber a qué vista regresar
    rol_antes_de_borrar = usuario.id_rol 
    
    try:
        if rol_antes_de_borrar == 2 and usuario.maestro_perfil:
            db.session.delete(usuario.maestro_perfil)
            proxima_vista = 'maestros'
        elif rol_antes_de_borrar == 3 and usuario.alumno_perfil:
            db.session.delete(usuario.alumno_perfil)
            proxima_vista = 'alumnos'
        else:
            proxima_vista = 'alumnos' # Default
            
        db.session.delete(usuario)
        db.session.commit()
        flash("Usuario eliminado correctamente", "success")
        
    except Exception as e:
        db.session.rollback()
        flash("No se puede eliminar el usuario porque tiene registros dependientes.", "error")
        proxima_vista = 'alumnos' if rol_antes_de_borrar == 3 else 'maestros'
        
    # CORRECCIÓN: Ahora pasamos el parámetro 'vista'
    return redirect(url_for('gestion_usuarios', vista=proxima_vista))

if __name__ == '__main__':
    app.run(debug=True)