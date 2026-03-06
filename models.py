from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Roles(db.Model):
    __tablename__ = 'roles'
    IdRol = db.Column('idrol', db.Integer, primary_key=True)
    NombreRol = db.Column('nombrerol', db.String(50))

class Usuarios(db.Model):
    __tablename__ = 'usuarios'
    IdUsuario = db.Column('idusuario', db.Integer, primary_key=True)
    Nombre = db.Column('nombre', db.String(100))
    Apellido = db.Column('apellido', db.String(100))
    Correo = db.Column('correo', db.String(100))
    Contrasena = db.Column('contrasena', db.String(255))
    IdRol = db.Column('idrol', db.Integer, db.ForeignKey('roles.idrol'))

class Grados(db.Model):
    __tablename__ = 'grados'
    IdGrado = db.Column('idgrado', db.Integer, primary_key=True)
    NombreGrado = db.Column('nombregrado', db.String(50))

class Secciones(db.Model):
    __tablename__ = 'secciones'
    IdSeccion = db.Column('idseccion', db.Integer, primary_key=True)
    NombreSeccion = db.Column('nombreseccion', db.String(10), nullable=False)
    IdGrado = db.Column('idgrado', db.Integer, db.ForeignKey('grados.idgrado'), nullable=False)

class Maestros(db.Model):
    __tablename__ = 'maestros'
    IdMaestro = db.Column('idmaestro', db.Integer, primary_key=True)
    IdUsuario = db.Column('idusuario', db.Integer, db.ForeignKey('usuarios.idusuario'))
    Especialidad = db.Column('especialidad', db.String(100))
    Biografia = db.Column('biografia', db.Text)

class Clases(db.Model):
    __tablename__ = 'clases'
    IdClase = db.Column('idclase', db.Integer, primary_key=True)
    NombreClase = db.Column('nombreclase', db.String(100), nullable=False)
    IdSeccion = db.Column('idseccion', db.Integer, db.ForeignKey('secciones.idseccion'), nullable=False)
    IdMaestro = db.Column('idmaestro', db.Integer, db.ForeignKey('maestros.idmaestro'), nullable=False)
    Periodo = db.Column('periodo', db.String(20))

class Tareas(db.Model):
    __tablename__ = 'tareas'
    IdTarea = db.Column('idtarea', db.Integer, primary_key=True)
    IdClase = db.Column('idclase', db.Integer, db.ForeignKey('clases.idclase'), nullable=False)
    Titulo = db.Column('titulo', db.String(100), nullable=False)
    Descripcion = db.Column('descripcion', db.Text)
    FechaEntrega = db.Column('fechaentrega', db.DateTime, nullable=False)
    FechaPublicacion = db.Column('fechapublicacion', db.DateTime, default=db.func.now())

class Notas(db.Model):
    __tablename__ = 'notas'
    IdNota = db.Column('idnota', db.Integer, primary_key=True)
    IdClase = db.Column('idclase', db.Integer, db.ForeignKey('clases.idclase'))
    IdAlumno = db.Column('idalumno', db.Integer)
    Nota = db.Column('nota', db.Numeric(5, 2))

class Alumnos(db.Model):
    __tablename__ = 'alumnos'
    IdAlumno = db.Column('idalumno', db.Integer, primary_key=True)
    IdUsuario = db.Column('idusuario', db.Integer, db.ForeignKey('usuarios.idusuario'), nullable=False)
    IdSeccion = db.Column('idseccion', db.Integer, db.ForeignKey('secciones.idseccion'), nullable=False)
    Nie = db.Column('nie', db.String(20))