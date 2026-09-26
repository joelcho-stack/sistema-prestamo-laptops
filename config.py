import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    # Intenta leer la variable DATABASE_URL de Render (Supabase)
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Si la URL viene de Render y empieza con "postgres://", la corregimos a "postgresql://"
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    else:
        # Si no está en Render (en tu PC local), usa tus datos locales de siempre
        conn = psycopg2.connect(
            host="localhost",
            database="inventario_lab",
            user="postgres",
            password="12345678",
            port="5432",
            cursor_factory=RealDictCursor
        )
        
    return conn