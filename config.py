class Config:
    # Estructura: postgresql://usuario:contraseña@localhost:puerto/nombre_bd
    # SQLALCHEMY_DATABASE_URI = "postgresql://postgres:gacm09032005@localhost:5432/EduPortal"
    SQLALCHEMY_DATABASE_URI = "postgresql://maxandino:aIGhDBiqsTXWIbBBnJ3zZxuT0fZow576@dpg-d6jmbqftskes73alv6u0-a.oregon-postgres.render.com:5432/eduportaldb"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "super_secret_key"