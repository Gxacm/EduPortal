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
    
    # Si borras un usuario, se borra su perfil de maestro o alumno automáticamente
    maestro_perfil = db.relationship('Maestros', backref='usuario', uselist=False, cascade="all, delete-orphan")
    alumno_perfil = db.relationship('Alumnos', backref='usuario', uselist=False, cascade="all, delete-orphan")

# 2. ACADÉMICO
class CiclosLectivos(db.Model):
    __tablename__ = 'ciclos_lectivos'
    id_cycle = db.Column(db.Integer, primary_key=True)
    nombre_ciclo = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=True)
    fecha_fin = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(15), default='INACTIVO') 

    clases = db.relationship('Clases', backref='ciclo', lazy=True)

class Grados(db.Model):
    __tablename__ = 'grados'
    id_grado = db.Column(db.Integer, primary_key=True)
    nombre_grado = db.Column(db.String(100), nullable=False)

    # Si borras un grado, borramos sus secciones y sus clases
    secciones = db.relationship('Secciones', backref='grado', lazy=True, cascade="all, delete-orphan")
    clases = db.relationship('Clases', backref='grado', lazy=True, cascade="all, delete-orphan")

class Secciones(db.Model):
    __tablename__ = 'secciones'
    id_seccion = db.Column(db.Integer, primary_key=True)
    nombre_seccion = db.Column(db.String(1), nullable=False)
    id_grado = db.Column(db.Integer, db.ForeignKey('grados.id_grado', ondelete='CASCADE'))
    
    alumnos = db.relationship('Alumnos', backref='seccion', lazy=True)
    
class Horarios(db.Model):
    __tablename__ = 'horarios'
    id_horario = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase', ondelete='CASCADE'), nullable=False)
    id_seccion = db.Column(db.Integer, db.ForeignKey('secciones.id_seccion', ondelete='CASCADE'), nullable=False)
    dia_semana = db.Column(db.String(15), nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)

    clase = db.relationship('Clases', backref=db.backref('bloques_horario', lazy=True))
    seccion = db.relationship('Secciones', backref=db.backref('horarios_seccion', lazy=True))

# 3. PERFILES
class Maestros(db.Model):
    __tablename__ = 'maestros'
    id_maestro = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), unique=True)
    especialidad = db.Column(db.String(100))
    
    clases = db.relationship('Clases', backref='maestro_titular', lazy=True)

class Alumnos(db.Model):
    __tablename__ = 'alumnos'
    id_alumno = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), unique=True)
    id_seccion = db.Column(db.Integer, db.ForeignKey('secciones.id_seccion', ondelete='SET NULL'))
    carnet = db.Column(db.String(20), unique=True)

# 4. OPERACIÓN Y AUDITORÍA
class Clases(db.Model):
    __tablename__ = 'clases'
    id_clase = db.Column(db.Integer, primary_key=True)
    nombre_clase = db.Column(db.String(100), nullable=False)
    
    # Si borras el maestro, la clase se queda sin maestro (SET NULL) en vez de borrarse
    id_maestro = db.Column(db.Integer, db.ForeignKey('maestros.id_maestro', ondelete='SET NULL'), nullable=True)
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclos_lectivos.id_cycle'))
    id_grado = db.Column(db.Integer, db.ForeignKey('grados.id_grado', ondelete='CASCADE'))
    
    # Si borras la clase, se borra TODO su rastro operativo
    tareas = db.relationship('Tareas', backref='clase', lazy=True, cascade="all, delete-orphan")
    asistencias = db.relationship('Asistencias', backref='clase', lazy=True, cascade="all, delete-orphan")
    anuncios = db.relationship('Anuncios', backref='clase', lazy=True, cascade="all, delete-orphan")

class Tareas(db.Model):
    __tablename__ = 'tareas'
    id_tarea = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase', ondelete='CASCADE'))
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_publicacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_entrega = db.Column(db.DateTime, nullable=False)
    
    # Si borras la tarea, se borran sus entregas y sus notas
    entregas = db.relationship('EntregasTareas', backref='tarea', lazy=True, cascade="all, delete-orphan")
    notas_tarea = db.relationship('Notas', backref='tarea_rel', lazy=True, cascade="all, delete-orphan")

class EntregasTareas(db.Model):
    __tablename__ = 'entregas_tareas'
    id_entrega = db.Column(db.Integer, primary_key=True)
    id_tarea = db.Column(db.Integer, db.ForeignKey('tareas.id_tarea', ondelete='CASCADE'))
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno', ondelete='CASCADE'))
    archivo_ruta = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='Entregado')

class Notas(db.Model):
    __tablename__ = 'notas'
    id_nota = db.Column(db.Integer, primary_key=True)
    id_tarea = db.Column(db.Integer, db.ForeignKey('tareas.id_tarea', ondelete='CASCADE'), nullable=True)
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen', ondelete='CASCADE'), nullable=True)
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno', ondelete='CASCADE'))
    calificacion = db.Column(db.Numeric(5,2))
    id_maestro_autor = db.Column(db.Integer, db.ForeignKey('maestros.id_maestro', ondelete='SET NULL'), nullable=True)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow)

    # Opcional: Relaciones para acceder fácil desde el objeto
    tarea = db.relationship('Tareas', backref='notas_asociadas')
    examen = db.relationship('Examenes', backref='notas_asociadas')

class Asistencias(db.Model):
    __tablename__ = 'asistencias'
    id_asistencia = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase', ondelete='CASCADE'))
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno', ondelete='CASCADE'))
    fecha = db.Column(db.Date, default=datetime.utcnow().date)
    estado = db.Column(db.String(20))

class Anuncios(db.Model):
    __tablename__ = 'anuncios'
    id_anuncio = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    dirigido_a = db.Column(db.String(20))
    id_usuario_autor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario', ondelete='CASCADE'))
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase', ondelete='CASCADE'), nullable=True)

# 5. MODELOS DE EXÁMENES
class Examenes(db.Model):
    __tablename__ = 'examenes'
    id_examen = db.Column(db.Integer, primary_key=True)
    id_clase = db.Column(db.Integer, db.ForeignKey('clases.id_clase', ondelete='CASCADE'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    modalidad = db.Column(db.String(50), nullable=False) # 'archivo', 'instrucciones', 'formulario'
    archivo_ruta = db.Column(db.String(255), nullable=True)
    fecha_limite = db.Column(db.DateTime, nullable=True)
    puntos_maximos = db.Column(db.Float, default=100.0)
    
    clase = db.relationship('Clases', backref=db.backref('examenes_rel', lazy=True))
    
    # Si borras el examen, se borran sus preguntas, entregas y notas
    preguntas = db.relationship('PreguntasExamen', backref='examen_rel', lazy=True, cascade="all, delete-orphan")
    entregas = db.relationship('EntregasExamenes', backref='examen_rel', lazy=True, cascade="all, delete-orphan")
    notas_examen = db.relationship('Notas', backref='examen_rel', lazy=True, cascade="all, delete-orphan")

class PreguntasExamen(db.Model):
    __tablename__ = 'preguntas_examen'
    id_pregunta = db.Column(db.Integer, primary_key=True)
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen', ondelete='CASCADE'), nullable=False)
    texto_pregunta = db.Column(db.Text, nullable=False)
    tipo_pregunta = db.Column(db.String(50), nullable=False)
    puntos = db.Column(db.Float, default=1.0)
    
    # Si se borra la pregunta, mueren sus opciones
    opciones = db.relationship('OpcionesPregunta', backref='pregunta_rel', lazy=True, cascade="all, delete-orphan")

class OpcionesPregunta(db.Model):
    __tablename__ = 'opciones_pregunta'
    id_opcion = db.Column(db.Integer, primary_key=True)
    id_pregunta = db.Column(db.Integer, db.ForeignKey('preguntas_examen.id_pregunta', ondelete='CASCADE'), nullable=False)
    texto_opcion = db.Column(db.String(255), nullable=False)
    es_correcta = db.Column(db.Boolean, default=False)

class EntregasExamenes(db.Model):
    __tablename__ = 'entregas_examenes'
    id_entrega_examen = db.Column(db.Integer, primary_key=True)
    id_examen = db.Column(db.Integer, db.ForeignKey('examenes.id_examen', ondelete='CASCADE'), nullable=False)
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumnos.id_alumno', ondelete='CASCADE'), nullable=False)
    archivo_ruta = db.Column(db.String(255), nullable=True)
    respuestas_json = db.Column(db.JSON, nullable=True) 
    estado = db.Column(db.String(50), default='entregado')
    fecha_entrega = db.Column(db.DateTime, default=db.func.current_timestamp())