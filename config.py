class Config:
    # Estructura: postgresql://usuario:contraseña@localhost:puerto/nombre_bd
    # SQLALCHEMY_DATABASE_URI = "postgresql://postgres:gacm09032005@localhost:5432/EduPortal"
    SQLALCHEMY_DATABASE_URI = "postgresql://maxandino:j498A1w3K4VzjyI6stlVivyi5Tg48GVI@dpg-d76ub76slomc73ake6vg-a.oregon-postgres.render.com/eduportaldb_5eim"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "super_secret_key"