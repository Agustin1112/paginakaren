import os
import cloudinary
import cloudinary.uploader
import mysql.connector
from mysql.connector import errorcode
from datetime import date
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Configuración de fecha
current_date = date.today()
current_year = current_date.year

# Conexión a base de datos
def dbConnection():
    connection = None
    try:
        connection = mysql.connector.connect(
            host = os.getenv("DB_HOST"),
            port = int(os.getenv("DB_PORT")),
            user = os.getenv("DB_USER"),
            passwd = os.getenv("DB_PASSWORD"),
            database = os.getenv("DB_NAME")
        )
    except errorcode as err:
        print(f"{err}")
        return None

    return connection

def closeConnection(connection, cursor):
    if connection.is_connected():
        cursor.close()
        connection.close()

# Traer datos
imagenes = []
testimonios = []

def getData(table_name):
    connection = dbConnection()
    cursor = connection.cursor()
    sql = "SELECT * FROM " + table_name
    try:
        cursor.execute(sql,)
        data = cursor.fetchall()
    except errorcode as err:
        print(f"{err}")
        data = []
    finally:
        closeConnection(connection, cursor)

    return data

# Configuración de subida de imágenes
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

cloudinary.config( 
    cloud_name = os.getenv("CLOUDINARY_USER"), 
    api_key = os.getenv("CLOUDINARY_API_KEY"), 
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure = True
)

# Configuración de correo
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

# ========= PÁGINAS PRINCIPALES =========

@app.route("/")
def home():
    return render_template("index.html", current_year=current_year)

@app.route("/about")
def about():
    return render_template("about.html", current_year=current_year)

@app.route("/services")
def services():
    return render_template("services.html", current_year=current_year)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        try:
            msg = Message(
                subject=f"Nuevo mensaje de {name}",
                sender=email,
                recipients=[os.getenv("MAIL_USERNAME")],
                body=f"De: {name} <{email}>\n\n{message}"
            )
            mail.send(msg)
            flash("Tu mensaje fue enviado correctamente. ¡Gracias!", "success")
        except Exception as e:
            print("Error al enviar mensaje:", e)
            flash("Error al enviar mensaje. Intentá más tarde.", "error")
        return redirect(url_for("contact"))
    return render_template("contact.html", current_year=current_year)

@app.route("/faq")
def faq():
    return render_template("faq.html", current_year=current_year)

# ========= ADMIN SIMPLE =========

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        clave = request.form.get("clave")
        if clave == os.getenv("ADMIN_KEY"):
            session["autorizado"] = True
            flash("Acceso autorizado ✅", "success")
            return redirect(url_for("admin_galeria"))
        else:
            flash("Clave incorrecta ❌", "error")
    return render_template("admin.html")

@app.route("/logout")
def logout():
    session.pop("autorizado", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("home"))

# ========= TESTIMONIOS =========

@app.route("/testimonios")
def testimonios():

    testimonios = getData("testimonies")

    data = testimonios

    if not session.get("autorizado"):
        data = [tsy for tsy in testimonios if tsy[3] == 1]

    return render_template("testimonios.html", testimonios=data, autorizado=session.get("autorizado"), current_year=current_year)

@app.route("/agregar-testimonio", methods=["GET", "POST"])
def agregar_testimonio():

    testimonios = getData("testimonies")

    if request.method == "POST":
        nombre = request.form.get("nombre")
        mensaje = request.form.get("mensaje")
        if nombre and mensaje:
            connection = dbConnection()
            cursor = connection.cursor()
            try:
                sql = "INSERT INTO testimonies (tsy_name, tsy_msg) VALUES (%s, %s)"
                cursor.execute(sql, (nombre, mensaje,))
                connection.commit()

                flash("Gracias por compartir tu testimonio ❤️ (Pendiente de aprobación)", "success")
            except errorcode as err:
                print(f"{err}")
                connection.rollback()
            finally:
                closeConnection(connection, cursor)

            return redirect(url_for("testimonios"))
        else:
            flash("Por favor, completá todos los campos.", "error")
    return render_template("agregar_testimonio.html", testimonios=testimonios)

@app.route("/aprobar-testimonio/<int:item_id>", methods=["GET", "POST"])
def aprobar_testimonio(item_id):
    if not session.get("autorizado"):
        return redirect(url_for("testimonios"))
    else:
        if request.method == "POST":
            connection = dbConnection()
            cursor = connection.cursor()
            try:
                sql = "UPDATE testimonies SET tsy_approved = %s WHERE tsy_id = %s"
                cursor.execute(sql, (1, item_id,))
                connection.commit()

                flash("Testimonio aprobado correctamente ✅", "success")
                return redirect(url_for("testimonios"))
            except errorcode as err:
                connection.rollback()
                print("Error aprobando testimonio:", err)
                flash("Error al aprobar testimonio", "error")
                return redirect(url_for("testimonios"))
            finally:
                closeConnection(connection, cursor)

        return render_template("testimonios.html")

@app.route("/eliminar-testimonio/<int:item_id>", methods=["POST"])
def eliminar_testimonio(item_id):
    clave = request.form.get("clave")
    if clave != os.getenv("ADMIN_KEY"):
        flash("Clave incorrecta ❌", "error")
        return redirect(url_for("testimonios"))

    connection = dbConnection()
    cursor = connection.cursor()
    try:
        sql = "DELETE FROM testimonies WHERE tsy_id = %s"
        cursor.execute(sql, (item_id,))
        connection.commit()

        flash("Testimonio eliminado correctamente ✅", "success")
    except errorcode as err:
        print(f"{err}")
        flash("Ocurrió un error al eliminar.", "error")
    finally:
        closeConnection(connection, cursor)

    return redirect(url_for("testimonios"))

@app.route("/editar-testimonio/<int:item_id>", methods=["GET", "POST"])
def editar_testimonio(item_id):

    testimonios = getData("testimonies")

    tsy_filter = [tsy for tsy in testimonios if tsy[0] == item_id]

    for result in tsy_filter:
        nombre = result[1]
        mensaje = result[2]

    if not session.get("autorizado"):
        return redirect(url_for("testimonios"))
    else:
        if request.method == "POST":
            nuevo_nombre = request.form.get("nombre")
            nuevo_mensaje = request.form.get("mensaje")

            if len(nuevo_nombre) == 0:
                nuevo_nombre = nombre
            
            if len(nuevo_mensaje) == 0:
                nuevo_mensaje = mensaje

            if nuevo_nombre or nuevo_mensaje:
                connection = dbConnection()
                cursor = connection.cursor()
                try:
                    sql = "UPDATE testimonies SET tsy_name = %s, tsy_msg = %s WHERE tsy_id = %s"
                    cursor.execute(sql, (nuevo_nombre, nuevo_mensaje, item_id,))
                    connection.commit()

                    flash("Testimonio actualizado correctamente ✅", "success")
                    return redirect(url_for("testimonios"))
                except errorcode as err:
                    connection.rollback()
                    print("Error editando testimonio:", err)
                    flash("Error al editar testimonio", "error")
                    return redirect(url_for("testimonios"))
                finally:
                    closeConnection(connection, cursor)
            else:
                flash("No se ha hecho ningún cambio.", "error")

        return render_template("editar_testimonio.html", nombre=nombre, mensaje=mensaje)

# ========= RESULTADOS =========

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/resultados", methods=["GET"])
def resultados():
    imagenes = getData("images")

    return render_template("resultados.html", imagenes=imagenes, autorizado=session.get("autorizado"), current_year=current_year)

@app.route("/admin/galeria", methods=["GET", "POST"])
def admin_galeria():
    if not session.get("autorizado"):
        return redirect(url_for("admin"))

    imagenes = getData("images")

    if request.method == "POST":
        if 'imagen' not in request.files:
            flash("No se envió ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        file = request.files["imagen"]
        if file.filename == "":
            flash("No seleccionaste ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        if file and allowed_file(file.filename):
            response = cloudinary.uploader.upload(file)
            secure_url = response["secure_url"]

            connection = dbConnection()
            cursor = connection.cursor()
            try:
                sql = "INSERT INTO images (img_url) VALUES (%s)"
                cursor.execute(sql, (secure_url,))
                connection.commit()

                flash("Imagen subida correctamente ✅", "success")
            except errorcode as err:
                connection.rollback()
                print(f"{err}")
            finally:
                closeConnection(connection, cursor)

            return redirect(url_for("admin_galeria"))
        else:
            flash("Formato no permitido. Solo PNG, JPG, JPEG y GIF.", "error")

    return render_template("admin_galeria.html", imagenes=imagenes, current_year=current_year)

@app.route("/admin/galeria/eliminar/<int:item_id>", methods=["GET", "POST"])
def eliminar_resultado(item_id):
    if not session.get("autorizado"):
        return redirect(url_for("admin"))

    connection = dbConnection()
    cursor = connection.cursor()
    try:
        sql = "DELETE FROM images WHERE img_id = %s"
        cursor.execute(sql, (item_id,))
        connection.commit()

        flash("Imagen eliminada correctamente ✅", "success")
    except errorcode as err:
        print(f"{err}")
        flash("Ocurrió un error al eliminar la imagen.", "error")
    finally:
        closeConnection(connection, cursor)

    return redirect(url_for("admin_galeria"))

# ========= FORMULARIO PAR-Q =========

@app.route("/parq", methods=["GET", "POST"])
def parq():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        edad = request.form.get("edad")
        sexo = request.form.get("sexo")
        profesion = request.form.get("profesion")
        disponibilidad = request.form.get("disponibilidad")
        objetivos = request.form.get("objetivos")
        otras_actividades = request.form.get("otras_actividades")
        lesiones = request.form.get("lesiones")
        peso_estatura = request.form.get("peso_estatura")
        observaciones = request.form.get("observaciones")
        firma = request.form.get("firma")

        # Respuestas PAR-Q
        respuestas = []
        for i in range(1, 8):
            si = request.form.get(f"q{i}_si")
            no = request.form.get(f"q{i}_no")
            respuesta = "Sí" if si else "No" if no else "No contestó"
            respuestas.append((i, respuesta))

        try:
            html = render_template(
                "email_parq.html",
                nombre=nombre,
                edad=edad,
                sexo=sexo,
                profesion=profesion,
                disponibilidad=disponibilidad,
                objetivos=objetivos,
                otras_actividades=otras_actividades,
                lesiones=lesiones,
                peso_estatura=peso_estatura,
                respuestas=respuestas,
                observaciones=observaciones,
                firma=firma
            )

            msg = Message(
                subject=f"Nuevo CUESTIONARIO PAR-Q - {nombre}",
                recipients=[app.config['MAIL_USERNAME']],
                html=html
            )
            mail.send(msg)
            flash("Formulario enviado correctamente ✅", "success")
        except Exception as e:
            print("Error enviando PAR-Q:", e)
            flash("Error al enviar el formulario ❌", "error")

        return redirect(url_for("parq"))

    return render_template("parq.html")

# ========= EJECUTAR =========

if __name__ == "__main__":
    app.run(debug=True)
