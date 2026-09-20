import os
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from config import get_db_connection

# Librerías para generación de PDF
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_laboratorio_bti_bts_2026')

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cedula = request.form.get('cedula', '').strip()
        password = request.form.get('password', '').strip()

        if not cedula or not password:
            flash('Por favor, ingrese su cédula y contraseña.', 'warning')
            return render_template('login.html')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, apellido, password_hash, rol, curso, bachillerato, turno FROM usuarios WHERE cedula = %s;", (cedula,))
        usuario = cur.fetchone()
        cur.close()
        conn.close()

        if usuario and check_password_hash(usuario['password_hash'], password):
            session['usuario_id'] = usuario['id']
            session['nombre'] = usuario['nombre']
            session['apellido'] = usuario['apellido']
            session['rol'] = usuario['rol']
            session['curso'] = usuario.get('curso', '') or ''
            session['bachillerato'] = usuario.get('bachillerato', '') or ''
            
            if usuario['rol'] == 'admin':
                session['turno'] = ''
            else:
                session['turno'] = usuario.get('turno', '') or ''
            
            flash(f'¡Bienvenido/a, {usuario["nombre"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Cédula o contraseña incorrecta.', 'danger')

    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        cedula = request.form.get('cedula', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        bachillerato = request.form.get('bachillerato', '').strip()
        curso = request.form.get('curso', '').strip()
        turno = request.form.get('turno', '').strip()

        if not all([nombre, apellido, cedula, email, password, bachillerato, curso, turno]):
            flash('Todos los campos son obligatorios.', 'warning')
            return render_template('registro.html')

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM usuarios WHERE cedula = %s OR email = %s;", (cedula, email))
        if cur.fetchone():
            flash('La cédula o el correo electrónico ya se encuentran registrados.', 'danger')
            cur.close()
            conn.close()
            return render_template('registro.html')

        password_hash = generate_password_hash(password)

        try:
            cur.execute("""
                INSERT INTO usuarios (cedula, nombre, apellido, email, password_hash, bachillerato, curso, turno, rol)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'alumno');
            """, (cedula, nombre, apellido, email, password_hash, bachillerato, curso, turno))
            conn.commit()
            flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash('Ocurrió un error al registrar el usuario.', 'danger')
        finally:
            cur.close()
            conn.close()

    return render_template('registro.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.*, l.marca_modelo, l.numero_equipo, l.codigo
        FROM prestamos p
        LEFT JOIN laptops l ON p.laptop_id = l.id
        WHERE p.alumno_id = %s AND p.estado = 'en_uso'
        ORDER BY p.fecha_prestamo DESC;
    """, (usuario_id,))
    mis_prestamos = cur.fetchall()

    cur.execute("SELECT *, 'laptop' AS tipo_equipo FROM laptops ORDER BY id ASC;")
    laptops = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('dashboard.html', mis_prestamos=mis_prestamos, laptops=laptops)

@app.route('/prestar/<int:laptop_id>', methods=['POST', 'GET'])
def prestar(laptop_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM prestamos WHERE alumno_id = %s AND estado = 'en_uso';", (usuario_id,))
    conteo = cur.fetchone()
    total_activos = conteo['total'] if isinstance(conteo, dict) else conteo[0]

    if total_activos >= 3:
        flash('Has alcanzado el límite máximo de 3 equipos en préstamo simultáneamente.', 'warning')
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))

    ahora = datetime.now()
    fecha_hoy = ahora.strftime('%Y-%m-%d')
    hora_actual = ahora.strftime('%H:%M:%S')

    materia = request.form.get('materia', 'General').strip()

    try:
        if laptop_id == 0:
            descripcion_otro = request.form.get('descripcion_otro', '').strip()
            if descripcion_otro:
                cur.execute("""
                    INSERT INTO prestamos (alumno_id, descripcion_otro, fecha_prestamo, hora_prestamo, materia, estado)
                    VALUES (%s, %s, %s, %s, %s, 'en_uso');
                """, (usuario_id, descripcion_otro, fecha_hoy, hora_actual, materia))
                conn.commit()
                flash('Solicitud de dispositivo registrada.', 'success')
        else:
            cur.execute("""
                INSERT INTO prestamos (alumno_id, laptop_id, fecha_prestamo, hora_prestamo, materia, estado)
                VALUES (%s, %s, %s, %s, %s, 'en_uso');
            """, (usuario_id, laptop_id, fecha_hoy, hora_actual, materia))

            cur.execute("UPDATE laptops SET estado = 'en_uso' WHERE id = %s;", (laptop_id,))
            conn.commit()
            flash('Préstamo registrado exitosamente.', 'success')

    except Exception as e:
        conn.rollback()
        print("Error en BD:", e)
        flash('Error al procesar el préstamo.', 'danger')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/devolver/<int:prestamo_id>', methods=['POST', 'GET'])
def devolver(prestamo_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM prestamos WHERE id = %s AND estado = 'en_uso';", (prestamo_id,))
    prestamo = cur.fetchone()

    if not prestamo:
        flash('El préstamo no existe o ya fue devuelto.', 'warning')
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))

    ahora = datetime.now()
    fecha_hoy = ahora.strftime('%Y-%m-%d')
    hora_actual = ahora.strftime('%H:%M:%S')

    laptop_id = prestamo['laptop_id'] if isinstance(prestamo, dict) else prestamo[2]

    try:
        cur.execute("""
            UPDATE prestamos 
            SET estado = 'devuelto', fecha_devolucion = %s, hora_devolucion = %s 
            WHERE id = %s;
        """, (fecha_hoy, hora_actual, prestamo_id))

        if laptop_id:
            cur.execute("UPDATE laptops SET estado = 'disponible' WHERE id = %s;", (laptop_id,))

        conn.commit()
        flash('Devolución registrada correctamente.', 'success')
    except Exception as e:
        conn.rollback()
        print("Error en devolución:", e)
        flash('Error al registrar la devolución.', 'danger')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/admin')
def admin_panel():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if session.get('rol') != 'admin':
        flash('Acceso denegado: Esta sección es exclusiva para profesores.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.*, 
               u.nombre AS alumno_nombre, u.apellido AS alumno_apellido, u.cedula, u.curso, u.bachillerato,
               l.marca_modelo, l.numero_equipo, l.codigo
        FROM prestamos p
        JOIN usuarios u ON p.alumno_id = u.id
        LEFT JOIN laptops l ON p.laptop_id = l.id
        WHERE p.estado = 'en_uso'
        ORDER BY p.fecha_prestamo DESC;
    """)
    prestamos_activos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin.html', prestamos_activos=prestamos_activos)

@app.route('/admin/exportar_pdf')
def exportar_pdf():
    if 'usuario_id' not in session or session.get('rol') != 'admin':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('login'))

    mes = request.args.get('mes', '').strip()
    anio = request.args.get('anio', '').strip()

    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        SELECT p.*, 
               u.nombre AS alumno_nombre, u.apellido AS alumno_apellido, u.cedula, u.curso, u.bachillerato,
               l.marca_modelo, l.numero_equipo, l.codigo
        FROM prestamos p
        JOIN usuarios u ON p.alumno_id = u.id
        LEFT JOIN laptops l ON p.laptop_id = l.id
    """
    condiciones = []
    parametros = []

    if mes and mes.isdigit():
        condiciones.append("EXTRACT(MONTH FROM p.fecha_prestamo) = %s")
        parametros.append(int(mes))

    if anio and anio.isdigit():
        condiciones.append("EXTRACT(YEAR FROM p.fecha_prestamo) = %s")
        parametros.append(int(anio))

    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)

    sql += " ORDER BY p.fecha_prestamo DESC, p.hora_prestamo DESC;"

    cur.execute(sql, tuple(parametros))
    historial = cur.fetchall()
    cur.close()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=1,
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15
    )

    nombres_meses = {
        '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
        '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
        '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    subtexto_filtro = ""
    if mes in nombres_meses and anio:
        subtexto_filtro = f" - Mes de {nombres_meses[mes]} {anio}"
    elif mes in nombres_meses:
        subtexto_filtro = f" - Mes de {nombres_meses[mes]}"
    elif anio:
        subtexto_filtro = f" - Año {anio}"

    story.append(Paragraph(f"<b>Reporte Historial de Préstamos{subtexto_filtro} - Laboratorio de Informática</b>", title_style))
    fecha_generacion = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    story.append(Paragraph(f"Generado el: {fecha_generacion} | Total de registros: {len(historial)}", subtitle_style))

    data = [
        ["#", "Alumno", "Cédula", "Curso", "Equipo / Accesorio", "F. Préstamo", "H. Inicio", "Estado", "F. Devolución"]
    ]

    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')

    for i, p in enumerate(historial, start=1):
        alumno = f"{p['alumno_nombre']} {p['alumno_apellido']}"
        cedula = str(p['cedula'])
        curso_bach = f"{p.get('curso', '')} - {p.get('bachillerato', '')}"
        
        if p.get('laptop_id'):
            equipo = f"{p.get('marca_modelo', '')} ({p.get('codigo', '')})"
        else:
            equipo = p.get('descripcion_otro', 'Otro equipo')
            
        f_prestamo = str(p.get('fecha_prestamo', ''))
        h_prestamo = str(p.get('hora_prestamo', ''))
        estado = "EN USO" if p.get('estado') == 'en_uso' else "DEVUELTO"
        f_devolucion = f"{p.get('fecha_devolucion', '')} {p.get('hora_devolucion', '')}" if p.get('estado') == 'devuelto' else "-"

        data.append([
            Paragraph(str(i), cell_style),
            Paragraph(alumno, cell_bold),
            Paragraph(cedula, cell_style),
            Paragraph(curso_bach, cell_style),
            Paragraph(equipo, cell_style),
            Paragraph(f_prestamo, cell_style),
            Paragraph(h_prestamo, cell_style),
            Paragraph(estado, cell_style),
            Paragraph(f_devolucion, cell_style)
        ])

    table = Table(data, colWidths=[25, 120, 65, 85, 140, 70, 55, 60, 110])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#212529')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    story.append(table)
    doc.build(story)

    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    
    nombre_archivo = f"historial_prestamos_{mes if mes else 'todos'}_{anio if anio else 'todos'}.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
    return response

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
    