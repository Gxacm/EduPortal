from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# 1. SEGURIDAD Y ROLES
class Roles(db.Model):
    __tablename__ = 'roles'
    id_rol = db.Column(db.Integer, primary_key=True)
    nombre_rol = db.Column(db.String(20), nullable=False, unique=True)
    usuarios = db.relationship('Usuarios', backref='rol', lazy=True)

class Usuarios(db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    id_rol = db.Column(db.Integer, db.ForeignKey('roles.id_rol'))
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    maestro_perfil = db.relationship('Maestros', backref='usuario', uselist=False)
    alumno_perfil = db.relationship('Alumnos', backref='usuario', uselist=False)

# 2. ACADÉMICO
class CiclosLectivos(db.Model):
    __tablename__ = 'ciclos_lectivos'
    id_ciclo = db.Column(db.Integer, primary_key=True)
    nombre_ciclo = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.Boolean, default=True)
    clases = db.relationship('Clases', backref='ciclo', lazy=True)

class Grados(db.Model):
    __tablename__ = 'grados'
    id_grado = db.Column(db.Integer, primary_key=True)
    nombre_grado = db.Column(db.String(100), nullable=False)

    secciones = db.relationship('Secciones', backref='grado', lazy=True)
    clases = db.relationship('Clases', backref='grado', lazy=True)

class Secciones(db.Model):
    __tablename__ = 'secciones'
    id_seccion = db.Column(db.Integer, primary_key=True)
    nombre_seccion = db.Column(db.String(1), nullable=False)
    id_grado = db.Column(db.Integer, db.ForeignKey('grados.id_grado'))
    alumnos = db.relationship('Alumnos', backref='seccion', lazy=True)

# 3. PERFILES
class Maestros(db.Model):
    __tablename__ = 'maestros'
    id_maestro = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), unique=True)
    especialidad = db.Column(db.String(100))
    clases = db.relationship('Clases', backref='maestro_titular', lazy=True)

class Alumnos(db.Model):
    __tablename__ = 'alumnos'
    id_alumno = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), unique=True)
    id_seccion = db.Column(db.Integer, db.ForeignKey('secciones.id_seccion'))
    carnet = db.Column(db.String(20), unique=True)

# 4. OPERACIÓN Y AUDITORÍA
class Clases(db.Model):
    __tablename__ = 'clases'
    id_clase = db.Column(db.Integer, primary_key=True)
    nombre_clase = db.Column(db.String(100), nullable=False)
    id_maestro = db.Column(db.Integer, db.ForeignKey('maestros.id_maestro'))
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclos_lectivos.id_ciclo'))
    tareas = db.relationship('Tareas', backref='clase', lazy=True)
    id_grado = db.Column(db.Integer, db.ForeignKey('grados.id_grado'))

class Tareas(db.Model):
    __tablename__ = 'tareas'
    id_tarea = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase'))
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_entrega = db.Column(db.DateTime, nullable=False)
    entregas = db.relationship('EntregasTareas', backref='tarea', lazy=True)

class EntregasTareas(db.Model):
    __tablename__ = 'entregas_tareas'
    id_entrega = db.Column(db.Integer, primary_key=True)
    id_tarea = db.Column(db.Integer, db.ForeignKey('tareas.id_tarea'))
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno'))
    archivo_ruta = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='Entregado')

class Notas(db.Model):
    __tablename__ = 'notas'
    id_nota = db.Column(db.Integer, primary_key=True)
    id_tarea = db.Column(db.Integer, db.ForeignKey('tareas.id_tarea'), nullable=True) # Cambiado a nullable=True
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen'), nullable=True) # <--- AGREGA ESTA LÍNEA
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno'))
    calificacion = db.Column(db.Numeric(5,2))
    id_maestro_autor = db.Column(db.Integer, db.ForeignKey('maestros.id_maestro'))
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow)

    # Opcional: Relaciones para acceder fácil desde el objeto
    tarea = db.relationship('Tareas', backref='notas_tarea')
    examen = db.relationship('Examenes', backref='notas_examen')

class Asistencias(db.Model):
    __tablename__ = 'asistencias'
    id_asistencia = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase'))
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno'))
    fecha = db.Column(db.Date, default=datetime.utcnow().date)
    estado = db.Column(db.String(20))

class Anuncios(db.Model):
    __tablename__ = 'anuncios'
    id_anuncio = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    dirigido_a = db.Column(db.String(20))
    id_usuario_autor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================================================================
# ----------------------------- MODELOS DE EXÁMENES ----------------------------
# ==============================================================================

class Examenes(db.Model):
    __tablename__ = 'examenes'
    id_examen = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    modalidad = db.Column(db.String(50), nullable=False) # 'archivo', 'instrucciones', 'formulario'
    archivo_ruta = db.Column(db.String(255), nullable=True)
    fecha_limite = db.Column(db.DateTime, nullable=True)
    puntos_maximos = db.Column(db.Float, default=100.0)
    
    # Relación
    clase = db.relationship('Clases', backref=db.backref('examenes', lazy=True))

class PreguntasExamen(db.Model):
    __tablename__ = 'preguntas_examen'
    id_pregunta = db.Column(db.Integer, primary_key=True)
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen'), nullable=False)
    texto_pregunta = db.Column(db.Text, nullable=False)
    tipo_pregunta = db.Column(db.String(50), nullable=False) # 'opcion_multiple', 'abierta', 'verdadero_falso'
    puntos = db.Column(db.Float, default=1.0)
    
    # Relación
    examen = db.relationship('Examenes', backref=db.backref('preguntas', lazy=True, cascade="all, delete-orphan"))

class OpcionesPregunta(db.Model):
    __tablename__ = 'opciones_pregunta'
    id_opcion = db.Column(db.Integer, primary_key=True)
    id_pregunta = db.Column(db.Integer, db.ForeignKey('preguntas_examen.id_pregunta'), nullable=False)
    texto_opcion = db.Column(db.String(255), nullable=False)
    es_correcta = db.Column(db.Boolean, default=False)
    
    # Relación
    pregunta = db.relationship('PreguntasExamen', backref=db.backref('opciones', lazy=True, cascade="all, delete-orphan"))

class EntregasExamenes(db.Model):
    __tablename__ = 'entregas_examenes'
    id_entrega_examen = db.Column(db.Integer, primary_key=True)
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen'), nullable=False)
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno'), nullable=False)
    archivo_ruta = db.Column(db.String(255), nullable=True)
    respuestas_json = db.Column(db.JSON, nullable=True) 
    # calificacion = db.Column(db.Float, nullable=True)  <-- ELIMINA O COMENTA ESTA LÍNEA
    estado = db.Column(db.String(50), default='entregado')
    fecha_entrega = db.Column(db.DateTime, default=db.func.current_timestamp())