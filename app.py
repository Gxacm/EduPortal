from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
from config import Config
from models import db, Usuarios, Grados, Clases, Notas, Secciones, Maestros, Tareas, Alumnos 

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# ---------------- LOGIN ----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        
        # Mapeo automático a minúsculas gracias a models.py
        user = Usuarios.query.filter_by(Correo=correo, Contrasena=password).first()
        
        if user:
            session['user_id'] = user.IdUsuario
            session['rol'] = user.IdRol
            
            # Redirecciones usando url_for para mayor seguridad
            if user.IdRol == 1: return redirect(url_for('admin_dashboard'))
            elif user.IdRol == 2: return redirect(url_for('maestro_dashboard'))
            else: return redirect(url_for('alumno_dashboard'))
        
        # En lugar de un texto plano, usamos flash para el HTML
        flash("Correo o contraseña incorrectos. Intente de nuevo.")
        return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin')
def admin_dashboard():
    if session.get('rol') != 1: return redirect(url_for('login'))
    total_alumnos = Usuarios.query.filter_by(IdRol=3).count()
    total_maestros = Usuarios.query.filter_by(IdRol=2).count()
    return render_template('admin_dashboard.html', 
                           total_alumnos=total_alumnos, 
                           total_maestros=total_maestros, 
                           fecha_actual=datetime.now().strftime("%d/%m/%Y"))

# ---------------- MAESTRO DASHBOARD ----------------
@app.route('/maestro')
def maestro_dashboard():
    if session.get('rol') != 2: return redirect(url_for('login'))
    user_id = session.get('user_id')
    
    maestro_user = Usuarios.query.get(user_id)
    perfil_docente = Maestros.query.filter_by(IdUsuario=user_id).first()
    
    if not perfil_docente:
        return "Error: No se encontró perfil de maestro en la base de datos PostgreSQL."

    clases = Clases.query.filter_by(IdMaestro=perfil_docente.IdMaestro).all()
    grados_dict = {}
    
    for clase in clases:
        seccion = Secciones.query.get(clase.IdSeccion)
        if seccion:
            grado = Grados.query.get(seccion.IdGrado)
            if grado:
                if grado.IdGrado not in grados_dict:
                    grados_dict[grado.IdGrado] = {"grado": grado, "clases": []}
                grados_dict[grado.IdGrado]["clases"].append(clase)

    return render_template('maestro_dash.html', 
                           maestro=maestro_user, 
                           grados_data=list(grados_dict.values()), 
                           total_clases=len(clases))

# ---------------- GESTIÓN DE GRADO DETALLADO ----------------
@app.route('/maestro/grado/<int:id_grado>')
def gestionar_grado(id_grado):
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    grado = Grados.query.get_or_404(id_grado)
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(IdUsuario=user_id).first()
    
    secciones = Secciones.query.filter_by(IdGrado=id_grado).all()
    id_secciones = [s.IdSeccion for s in secciones]
    
    # Unión de tablas adaptada a la lógica de modelos en minúsculas de Postgres
    alumnos_grado = Usuarios.query.join(Alumnos, Usuarios.IdUsuario == Alumnos.IdUsuario)\
                    .filter(Alumnos.IdSeccion.in_(id_secciones)).all()
    
    clases_maestro = Clases.query.filter(
        Clases.IdMaestro == perfil.IdMaestro, 
        Clases.IdSeccion.in_(id_secciones)
    ).all()

    return render_template('maestro_gestion_grado.html', grado=grado, alumnos=alumnos_grado, clases=clases_maestro)

# ---------------- MAESTRO: TAREAS (ADAPTADO POSTGRES) ----------------
@app.route('/maestro/tareas/nueva', methods=['GET','POST'])
def crear_tarea():
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(IdUsuario=user_id).first()
    
    if request.method == 'POST':
        try:
            # Captura segura de datos
            id_clase = request.form.get('id_clase')
            titulo = request.form.get('titulo')
            descripcion = request.form.get('descripcion')
            fecha_str = request.form.get('fecha_entrega')
            
            # Conversión de fecha HTML a objeto Python
            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')

            nueva_tarea = Tareas(
                IdClase=id_clase, 
                Titulo=titulo, 
                Descripcion=descripcion, 
                FechaEntrega=fecha_dt
            )
            
            db.session.add(nueva_tarea)
            db.session.commit()
            
            return redirect(url_for('historial_tareas'))
        except Exception as e:
            db.session.rollback()
            return f"Error al insertar en Postgres: {e}"

    mis_clases = Clases.query.filter_by(IdMaestro=perfil.IdMaestro).all()
    return render_template('tareas_nuevas.html', clases=mis_clases)

@app.route('/maestro/tareas')
def historial_tareas():
    if session.get('rol') != 2: return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(IdUsuario=user_id).first()
    
    # Obtener IDs de clases para el filtro IN
    mis_clases = Clases.query.filter_by(IdMaestro=perfil.IdMaestro).all()
    mis_clases_ids = [c.IdClase for c in mis_clases]
    
    # Consulta de tareas ordenada por fecha descendente
    tareas = Tareas.query.filter(Tareas.IdClase.in_(mis_clases_ids)).order_by(Tareas.FechaEntrega.desc()).all()
    
    return render_template('tareas_historial.html', tareas=tareas)

# ---------------- MAESTRO: NOTAS ----------------
@app.route('/maestro/notas', methods=['GET','POST'])
def subir_notas():
    if session.get('rol') != 2: return redirect(url_for('login'))
    user_id = session.get('user_id')
    perfil = Maestros.query.filter_by(IdUsuario=user_id).first()

    if request.method == 'POST':
        try:
            nueva_nota = Notas(
                IdClase=request.form.get('id_clase'), 
                IdAlumno=request.form.get('id_alumno'), 
                Nota=request.form.get('nota')
            )
            db.session.add(nueva_nota)
            db.session.commit()
            return redirect(url_for('maestro_dashboard'))
        except Exception as e:
            db.session.rollback()
            return f"Error al subir nota: {e}"

    alumnos = Usuarios.query.filter_by(IdRol=3).all()
    clases = Clases.query.filter_by(IdMaestro=perfil.IdMaestro).all()
    return render_template('notas_subir.html', alumnos=alumnos, clases=clases)

# ---------------- ALUMNO DASHBOARD ----------------
@app.route('/alumno')
def alumno_dashboard():
    if session.get('rol') != 3: return redirect(url_for('login'))
    # Filtro por IdAlumno (Usuario conectado)
    notas = Notas.query.filter_by(IdAlumno=session.get('user_id')).all()
    return render_template('alumno_dash.html', notas=notas)

if __name__ == '__main__':
    app.run(debug=True)