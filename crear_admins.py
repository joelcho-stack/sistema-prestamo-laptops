from werkzeug.security import generate_password_hash
from config import get_db_connection

def registrar_administradores():
    # Lista de profesores y usuario de exposición
    admins = [
        {"nombre": "Junior", "apellido": "Escobar", "cedula": "4036844", "email": "junior.escobar@colegio.edu.py", "pass": "4036844"},
        {"nombre": "Erica", "apellido": "Duarte", "cedula": "4324362", "email": "erica.duarte@colegio.edu.py", "pass": "4324362"},
        {"nombre": "Gustavo", "apellido": "Villaverde", "cedula": "2001091", "email": "gustavo.villaverde@colegio.edu.py", "pass": "2001091"},
        {"nombre": "David", "apellido": "Espinola", "cedula": "5432100", "email": "david.espinola@colegio.edu.py", "pass": "5432100"},
        {"nombre": "Rodrigo", "apellido": "Frutos", "cedula": "123456", "email": "rodrigo.frutos@colegio.edu.py", "pass": "123456"}
    ]

    conn = get_db_connection()
    cur = conn.cursor()

    for admin in admins:
        # Verificar si la cédula ya existe
        cur.execute("SELECT id FROM usuarios WHERE cedula = %s;", (admin["cedula"],))
        existe = cur.fetchone()

        if not existe:
            password_hash = generate_password_hash(admin["pass"])
            cur.execute("""
                INSERT INTO usuarios (cedula, nombre, apellido, email, password_hash, rol, bachillerato, curso, turno)
                VALUES (%s, %s, %s, %s, %s, 'admin', 'DOCENTE', 'ENCARGADO', 'manana');
            """, (admin["cedula"], admin["nombre"], admin["apellido"], admin["email"], password_hash))
            print(f"✅ Administrador registrado: {admin['nombre']} {admin['apellido']} (CI: {admin['cedula']})")
        else:
            # Si ya existía, aseguramos que tenga rol de admin
            cur.execute("UPDATE usuarios SET rol = 'admin' WHERE cedula = %s;", (admin["cedula"],))
            print(f"ℹ️ El usuario CI {admin['cedula']} ya existía, se actualizó su rol a 'admin'.")

    conn.commit()
    cur.close()
    conn.close()
    print("\n🎉 ¡Proceso terminado con éxito!")

if __name__ == '__main__':
    registrar_administradores() 