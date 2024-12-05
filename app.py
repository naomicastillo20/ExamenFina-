import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from fpdf import FPDF
import pandas as pd
import io
from io import BytesIO
import sqlite3
from functools import wraps

# Configuración básica de la aplicación
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Cambia esta clave en producción

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Conexión a la base de datos SQLite
def conectar_bd():
    db_path = os.path.join(os.path.dirname(__file__), 'cuentas_por_pagar.db')
    return sqlite3.connect(db_path)

# Modelo de Usuario
class User(UserMixin):
    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Carga del usuario desde la base de datos
@login_manager.user_loader
def load_user(user_id):
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()

    if user_data:
        return User(id=user_data[0], username=user_data[1], password_hash=user_data[2], role=user_data[3])
    return None

# Formulario de Login usando Flask-WTF
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

# Ruta para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Verificar usuario en la base de datos
        with conectar_bd() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios WHERE username = ?', (username,))
            user_data = cursor.fetchone()

        if user_data:
            user = User(id=user_data[0], username=user_data[1], password_hash=user_data[2], role=user_data[3])
            if user.check_password(password):
                login_user(user)
                flash('Inicio de sesión exitoso', 'success')
                return redirect(url_for('index'))
            else:
                flash('Contraseña incorrecta', 'danger')
        else:
            flash('Usuario no encontrado', 'danger')

    return render_template('login.html', form=form)

def role_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role != role and current_user.role != 'admin':
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('index'))  # Redirige a la página principal
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# Ruta para cerrar sesión
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# Ruta principal
@app.route('/')
@login_required
def index():
    # Redirige según el rol
    if current_user.role == 'admin':
        return render_template('index.html', admin=True)
    else:
        return render_template('index.html', admin=False)


# Rutas de proveedores
@app.route('/agregar_proveedor', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def agregar_proveedor():
    if request.method == 'POST':
        id_proveedor = request.form['id_proveedor']
        nombre = request.form['nombre']
        balance = request.form['balance']
        
        with conectar_bd() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO proveedores (id_proveedor, nombre, balance) VALUES (?, ?, ?)', (id_proveedor, nombre, balance))
            conn.commit()
        return redirect('/listar_proveedores')
    return render_template('agregar_proveedor.html')

@app.route('/editar_proveedor/<int:id_proveedor>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def editar_proveedor(id_proveedor):
    with conectar_bd() as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            # Obtener datos del formulario
            nombre = request.form.get('nombre')
            balance = request.form.get('balance')

            # Actualizar la base de datos
            cursor.execute(
                'UPDATE proveedores SET nombre = ?, balance = ? WHERE id_proveedor = ?',
                (nombre, balance, id_proveedor)
            )
            conn.commit()
            return redirect('/listar_proveedores')
        
        # Obtener el proveedor actual para mostrar en el formulario de edición
        cursor.execute('SELECT * FROM proveedores WHERE id_proveedor = ?', (id_proveedor,))
        proveedor = cursor.fetchone()

    return render_template('editar_proveedor.html', proveedor=proveedor)


@app.route('/eliminar_proveedor/<int:id_proveedor>', methods=['POST'])
@login_required
@role_required('admin')
def eliminar_proveedor(id_proveedor):
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM proveedores WHERE id_proveedor = ?', (id_proveedor,))
        conn.commit()
    return redirect('/listar_proveedores')

@app.route('/listar_proveedores')
@login_required
@role_required('admin')
def listar_proveedores():
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM proveedores')
        proveedores = cursor.fetchall()
    return render_template('listar_proveedores.html', proveedores=proveedores)


@app.route('/listar_transacciones', methods=['GET'])
@login_required
@role_required('admin')
def listar_transacciones():
    transaccion_filtro = request.args.get('id_transaccion')
    proveedor_filtro = request.args.get('proveedor_id')
    tipo_filtro = request.args.get('tipo_movimiento')
    monto_filtro = request.args.get('monto')


    query = 'SELECT * FROM transacciones WHERE 1=1'
    params = []

    if tipo_filtro:
        query += ' AND tipo_movimiento = ?'
        params.append(tipo_filtro)
    if proveedor_filtro:
        query += ' AND id_proveedor LIKE ?'
        params.append(f'%{proveedor_filtro}%')
    if transaccion_filtro:
        query += ' AND id_transaccion LIKE ?'
        params.append(f'%{transaccion_filtro}%')
    if monto_filtro:
        query += ' AND monto = ?'
        params.append(monto_filtro)

    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        transacciones = cursor.fetchall()

    return render_template('listar_transacciones.html', transacciones=transacciones)


@app.route('/agregar_transaccion', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def agregar_transaccion():
    if request.method == 'POST':
        id_proveedor = request.form['id_proveedor']
        monto = float(request.form['monto'])
        tipo_movimiento = request.form['tipo_movimiento']

        with conectar_bd() as conn:
            cursor = conn.cursor()

            # Verificar si el proveedor existe
            cursor.execute('SELECT balance FROM proveedores WHERE id_proveedor = ?', (id_proveedor,))
            proveedor = cursor.fetchone()

            if not proveedor:
                flash('El proveedor no existe.', 'danger')
                return redirect('/listar_transacciones')

            balance_actual = proveedor[0]

            # Calcular el nuevo balance
            if tipo_movimiento == 'DB':
                nuevo_balance = balance_actual - monto
            elif tipo_movimiento == 'CR':
                nuevo_balance = balance_actual + monto
            else:
                flash('Tipo de movimiento inválido.', 'danger')
                return redirect('/listar_transacciones')

            try:
                # Insertar la transacción
                cursor.execute('''
                    INSERT INTO transacciones (id_proveedor, tipo_movimiento, monto)
                    VALUES (?, ?, ?)
                ''', (id_proveedor, tipo_movimiento, monto))

                # Actualizar el balance del proveedor
                cursor.execute('UPDATE proveedores SET balance = ? WHERE id_proveedor = ?', (nuevo_balance, id_proveedor))

                # Si es un pago (CR), verificar y eliminar la factura correspondiente
                if tipo_movimiento == 'CR':
                    cursor.execute('''
                        SELECT id_factura FROM facturas 
                        WHERE id_proveedor = ? AND monto = ?
                    ''', (id_proveedor, monto))
                    factura = cursor.fetchone()

                    if factura:
                        cursor.execute('DELETE FROM facturas WHERE id_factura = ?', (factura[0],))
                        flash('Factura pagada y eliminada con éxito.', 'success')

                conn.commit()
            except sqlite3.Error as e:
                flash(f'Error al registrar la transacción: {e}', 'danger')
                conn.rollback()

        return redirect('/listar_transacciones')

    # Obtener proveedores para el formulario
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id_proveedor, nombre FROM proveedores')
        proveedores = cursor.fetchall()

    return render_template('agregar_transaccion.html', proveedores=proveedores)


@app.route('/editar_transaccion/<int:id_transaccion>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def editar_transaccion(id_transaccion):
    with conectar_bd() as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            # Obtener datos del formulario
            id_proveedor = request.form.get('id_proveedor')
            tipo_movimiento = request.form.get('tipo_movimiento')
            monto = float(request.form.get('monto'))

            # Obtener los datos actuales de la transacción antes de actualizar
            cursor.execute('SELECT id_proveedor, tipo_movimiento, monto FROM transacciones WHERE id_transaccion = ?', (id_transaccion,))
            transaccion_actual = cursor.fetchone()

            if not transaccion_actual:
                flash("La transacción no existe.", "danger")
                return redirect('/listar_transacciones')

            id_proveedor_actual, tipo_movimiento_actual, monto_actual = transaccion_actual

            # Revertir el balance del proveedor con la transacción actual
            if tipo_movimiento_actual == 'DB':
                balance_ajustado = monto_actual
            elif tipo_movimiento_actual == 'CR':
                balance_ajustado = -monto_actual

            cursor.execute('UPDATE proveedores SET balance = balance + ? WHERE id_proveedor = ?',
                           (balance_ajustado, id_proveedor_actual))

            # Aplicar el nuevo impacto de la transacción editada
            if tipo_movimiento == 'DB':
                balance_ajustado = -monto
            elif tipo_movimiento == 'CR':
                balance_ajustado = monto

            cursor.execute('UPDATE proveedores SET balance = balance + ? WHERE id_proveedor = ?',
                           (balance_ajustado, id_proveedor))

            # Actualizar la transacción en la base de datos
            cursor.execute(
                '''UPDATE transacciones 
                   SET id_proveedor = ?, tipo_movimiento = ?, monto = ? 
                   WHERE id_transaccion = ?''',
                (id_proveedor, tipo_movimiento, monto, id_transaccion)
            )
            conn.commit()
            flash("Transacción actualizada y balance del proveedor ajustado.", "success")
            return redirect('/listar_transacciones')

        # Obtener la transacción actual para mostrar en el formulario de edición
        cursor.execute('SELECT * FROM transacciones WHERE id_transaccion = ?', (id_transaccion,))
        transaccion = cursor.fetchone()

    return render_template('editar_transaccion.html', transaccion=transaccion)


@app.route('/eliminar_transaccion/<int:id_transaccion>', methods=['POST'])
@login_required
@role_required('admin')
def eliminar_transaccion(id_transaccion):
    with conectar_bd() as conn:
        cursor = conn.cursor()
        # Eliminar la transacción de la base de datos
        cursor.execute('DELETE FROM transacciones WHERE id_transaccion = ?', (id_transaccion,))
        conn.commit()
    return redirect('/listar_transacciones')


# Ruta para agregar factura
@app.route('/agregar_factura', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def agregar_factura():
    if request.method == 'POST':
        id_proveedor = request.form['id_proveedor']
        monto = float(request.form['monto'])
        descripcion = request.form.get('descripcion', '')
        fecha_emision = request.form['fecha_emision']
        fecha_vencimiento = request.form['fecha_vencimiento']

        with conectar_bd() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO facturas (id_proveedor, monto, descripcion, fecha_emision, fecha_vencimiento)
                    VALUES (?, ?, ?, ?, ?)
                ''', (id_proveedor, monto, descripcion, fecha_emision, fecha_vencimiento))
                conn.commit()
                flash('Factura agregada con éxito.', 'success')
            except sqlite3.Error as e:
                flash(f'Error al agregar la factura: {e}', 'danger')
                conn.rollback()

        return redirect('/listar_facturas')

    # Obtener la lista de proveedores para mostrar en el formulario
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id_proveedor, nombre FROM proveedores')
        proveedores = cursor.fetchall()

    # Pasar los proveedores al renderizado de la plantilla
    return render_template('agregar_factura.html', proveedores=proveedores)



# Ruta para listar facturas
@app.route('/listar_facturas')
@login_required
@role_required('admin')
def listar_facturas():
    with conectar_bd() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT f.id_factura, f.id_proveedor, f.monto, f.descripcion, f.fecha_emision, f.fecha_vencimiento, p.nombre FROM facturas f JOIN proveedores p ON f.id_proveedor = p.id_proveedor')
        facturas = cursor.fetchall()

    return render_template('listar_facturas.html', facturas=facturas)


# Ruta para editar factura
@app.route('/editar_factura/<int:id_factura>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def editar_factura(id_factura):
    with conectar_bd() as conn:
        cursor = conn.cursor()

        if request.method == 'POST':
            id_proveedor = request.form['id_proveedor']
            monto = float(request.form['monto'])
            descripcion = request.form.get('descripcion', '')
            fecha_emision = request.form['fecha_emision']
            fecha_vencimiento = request.form['fecha_vencimiento']

            try:
                cursor.execute('''
                    UPDATE facturas
                    SET id_proveedor = ?, monto = ?, descripcion = ?, fecha_emision = ?, fecha_vencimiento = ?
                    WHERE id_factura = ?
                ''', (id_proveedor, monto, descripcion, fecha_emision, fecha_vencimiento, id_factura))
                conn.commit()
                flash('Factura actualizada con éxito.', 'success')
                return redirect('/listar_facturas')
            except sqlite3.Error as e:
                flash(f'Error al actualizar la factura: {e}', 'danger')
                conn.rollback()

        # Obtener la factura actual para mostrar en el formulario de edición
        cursor.execute('SELECT * FROM facturas WHERE id_factura = ?', (id_factura,))
        factura = cursor.fetchone()

        # Obtener la lista de proveedores para el selector
        cursor.execute('SELECT id_proveedor, nombre FROM proveedores')
        proveedores = cursor.fetchall()

    return render_template('editar_factura.html', factura=factura, proveedores=proveedores)


@app.route('/eliminar_factura/<int:id_factura>', methods=['POST'])
@login_required
@role_required('admin')
def eliminar_factura(id_factura):
    with conectar_bd() as conn:
        cursor = conn.cursor()

        try:
            # Verificar si la factura existe
            cursor.execute('SELECT id_proveedor, monto FROM facturas WHERE id_factura = ?', (id_factura,))
            factura = cursor.fetchone()

            if not factura:
                flash('Factura no encontrada.', 'danger')
                return redirect('/listar_facturas')

            id_proveedor, monto = factura

            # Eliminar la factura
            cursor.execute('DELETE FROM facturas WHERE id_factura = ?', (id_factura,))
            conn.commit()

            flash(f'Factura con ID {id_factura} eliminada correctamente.', 'success')
        except sqlite3.Error as e:
            flash(f'Error al eliminar la factura: {e}', 'danger')
            conn.rollback()

    return redirect('/listar_facturas')

@app.route('/generar_reporte', methods=['POST'])
def generar_reporte():
    try:
        tabla = request.form.get('tabla')
        formato = request.form.get('formato')

        # Verifica que la tabla seleccionada sea válida
        if tabla not in ['proveedores', 'transacciones', 'facturas']:
            return "Tabla no válida", 400

        # Conexión a la base de datos y carga de datos en un DataFrame
        conn = conectar_bd()
        query = f'SELECT * FROM {tabla}'
        df = pd.read_sql_query(query, conn)
        conn.close()

        if formato == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(200, 10, txt=f'Reporte de {tabla.capitalize()}', ln=True, align='C')

            # Configurar la fuente para el contenido
            pdf.set_font('Arial', '', 10)

            # Agregar contenido de la tabla
            for _, row in df.iterrows():
                texto = ' - '.join([f'{col}: {str(row[col])}' for col in df.columns])
                pdf.multi_cell(0, 10, texto)

            buffer = io.BytesIO()
            pdf_output = pdf.output(dest='S').encode('latin1')
            buffer.write(pdf_output)
            buffer.seek(0)

            # Enviar el archivo PDF como respuesta
            print("PDF generado correctamente")
            return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='reporte.pdf')

        elif formato == 'excel':
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Reporte', index=False)
                # No se necesita llamar a writer.save(), el archivo se guarda automáticamente al salir del contexto
            buffer.seek(0)

            # Guarda el archivo temporalmente para depuración
            with open('reporte_temporal.xlsx', 'wb') as f:
                f.write(buffer.getvalue())

            print("Excel generado correctamente")
            # Enviar el archivo Excel como respuesta
            return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name='reporte.xlsx')

        else:
            return "Formato no válido", 400

    except Exception as e:
        print(f"Error: {str(e)}")
        return f"Se ha producido un error: {str(e)}", 500






# Simulación de una función para obtener los datos de la tabla seleccionada
def obtener_datos(tabla):
    # Aquí deberías realizar una consulta a la base de datos para obtener los datos de la tabla
    # Esta es una simulación con datos de ejemplo.
    if tabla == 'proveedores':
        columnas = ['ID', 'Nombre', 'Monto']
        datos = [
            [1, 'Proveedor A', 1000],
            [2, 'Proveedor B', 1500]
        ]
    elif tabla == 'transacciones':
        columnas = ['ID', 'Fecha', 'Monto']
        datos = [
            [1, '2024-12-01', 500],
            [2, '2024-12-02', 300]
        ]
    elif tabla == 'facturas':
        columnas = ['ID', 'Fecha Emisión', 'Monto']
        datos = [
            [1, '2024-12-01', 700],
            [2, '2024-12-02', 800]
        ]
    return columnas, datos

# Función para generar un archivo PDF
def generar_pdf(columnas, datos, nombre_reporte):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(200, 10, txt=f'Reporte de {nombre_reporte}', ln=True, align='C')

    pdf.set_font('Arial', '', 12)
    pdf.ln(10)

    # Agregar encabezados
    pdf.set_font('Arial', 'B', 12)
    for columna in columnas:
        pdf.cell(40, 10, columna, 1)
    pdf.ln()

    # Agregar los datos
    pdf.set_font('Arial', '', 12)
    for fila in datos:
        for dato in fila:
            pdf.cell(40, 10, str(dato), 1)
        pdf.ln()

    # Guardar el PDF en un objeto BytesIO
    buffer = BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')  # Genera la salida PDF como una cadena de bytes
    buffer.write(pdf_output)
    buffer.seek(0)  # Mover el puntero al inicio del buffer

    return buffer

# Función para generar un archivo Excel
def generar_excel(columnas, datos, tabla):
    df = pd.DataFrame(datos, columns=columnas)
    excel_output = BytesIO()
    writer = pd.ExcelWriter(excel_output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Reporte')
    writer.save()
    excel_output.seek(0)
    return excel_output

@app.route('/reportes', methods=['GET', 'POST'])
def reportes():
    if request.method == 'GET':
        return render_template('reportes.html')

    if request.method == 'POST':
        tabla = request.form.get('tabla')
        formato = request.form.get('formato')

        if tabla not in ['proveedores', 'transacciones', 'facturas']:
            return "Error: Tabla no válida."

        columnas, datos = obtener_datos(tabla)

        if formato == 'pdf':
            pdf_output = generar_pdf(columnas, datos, tabla)
            return send_file(
                pdf_output, 
                as_attachment=True, 
                attachment_filename=f'reporte_{tabla}.pdf', 
                mimetype='application/pdf'
            )
        elif formato == 'excel':
            excel_output = generar_excel(columnas, datos, tabla)
            return send_file(
                excel_output, 
                as_attachment=True, 
                attachment_filename=f'reporte_{tabla}.xlsx', 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return "Error: Formato no soportado."
        

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)
