import os
import cloudinary
import cloudinary.uploader
import mysql.connector
from datetime import date
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-temporal")

# Configuración de fecha
current_date = date.today()
current_year = current_date.year

# =========================
# CONEXIÓN A BASE DE DATOS
# =========================

def dbConnection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            passwd=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        return connection
    except Exception as err:
        print(f"ERROR DB CONNECTION: {err}")
        return None


def closeConnection(connection, cursor=None):
    try:
        if cursor is not None:
            cursor.close()
    except Exception as err:
        print(f"ERROR CLOSING CURSOR: {err}")

    try:
        if connection is not None and connection.is_connected():
            connection.close()
    except Exception as err:
        print(f"ERROR CLOSING CONNECTION: {err}")


# =========================
# TRAER DATOS
# =========================

def getData(table_name):
    connection = dbConnection()

    if connection is None:
        print(f"No se pudo conectar a la base para consultar la tabla: {table_name}")
        return []

    cursor = connection.cursor()
    sql = f"SELECT * FROM {table_name}"

    try:
        cursor.execute(sql)
        data = cursor.fetchall()
        return data
    except Exception as err:
        print(f"ERROR GET DATA ({table_name}): {err}")
        return []
    finally:
        closeConnection(connection, cursor)


# =========================
# CONFIGURACIÓN CLOUDINARY
# =========================

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_USER"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


# =========================
# CONFIGURACIÓN DE CORREO
# =========================

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)


# =========================
# UTILIDADES
# =========================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# PÁGINAS PRINCIPALES
# =========================

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


# =========================
# ADMIN SIMPLE
# =========================

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


# =========================
# TESTIMONIOS
# =========================

@app.route("/testimonios")
def testimonios():
    testimonios_data = getData("testimonies")
    data = testimonios_data

    if not session.get("autorizado"):
        data = [tsy for tsy in testimonios_data if len(tsy) > 3 and tsy[3] == 1]

    return render_template(
        "testimonios.html",
        testimonios=data,
        autorizado=session.get("autorizado"),
        current_year=current_year
    )


@app.route("/agregar-testimonio", methods=["GET", "POST"])
def agregar_testimonio():
    testimonios_data = getData("testimonies")

    if request.method == "POST":
        nombre = request.form.get("nombre")
        mensaje = request.form.get("mensaje")

        if nombre and mensaje:
            connection = dbConnection()

            if connection is None:
                flash("No se pudo conectar a la base de datos.", "error")
                return redirect(url_for("testimonios"))

            cursor = connection.cursor()
            try:
                sql = "INSERT INTO testimonies (tsy_name, tsy_msg) VALUES (%s, %s)"
                cursor.execute(sql, (nombre, mensaje))
                connection.commit()
                flash("Gracias por compartir tu testimonio ❤️ (Pendiente de aprobación)", "success")
            except Exception as err:
                print(f"ERROR INSERT TESTIMONIO: {err}")
                connection.rollback()
                flash("Ocurrió un error al guardar el testimonio.", "error")
            finally:
                closeConnection(connection, cursor)

            return redirect(url_for("testimonios"))
        else:
            flash("Por favor, completá todos los campos.", "error")

    return render_template("agregar_testimonio.html", testimonios=testimonios_data, current_year=current_year)


@app.route("/aprobar-testimonio/<int:item_id>", methods=["GET", "POST"])
def aprobar_testimonio(item_id):
    if not session.get("autorizado"):
        return redirect(url_for("testimonios"))

    if request.method == "POST":
        connection = dbConnection()

        if connection is None:
            flash("No se pudo conectar a la base de datos.", "error")
            return redirect(url_for("testimonios"))

        cursor = connection.cursor()
        try:
            sql = "UPDATE testimonies SET tsy_approved = %s WHERE tsy_id = %s"
            cursor.execute(sql, (1, item_id))
            connection.commit()

            flash("Testimonio aprobado correctamente ✅", "success")
            return redirect(url_for("testimonios"))
        except Exception as err:
            connection.rollback()
            print("Error aprobando testimonio:", err)
            flash("Error al aprobar testimonio", "error")
            return redirect(url_for("testimonios"))
        finally:
            closeConnection(connection, cursor)

    return redirect(url_for("testimonios"))


@app.route("/eliminar-testimonio/<int:item_id>", methods=["POST"])
def eliminar_testimonio(item_id):
    clave = request.form.get("clave")

    if clave != os.getenv("ADMIN_KEY"):
        flash("Clave incorrecta ❌", "error")
        return redirect(url_for("testimonios"))

    connection = dbConnection()

    if connection is None:
        flash("No se pudo conectar a la base de datos.", "error")
        return redirect(url_for("testimonios"))

    cursor = connection.cursor()
    try:
        sql = "DELETE FROM testimonies WHERE tsy_id = %s"
        cursor.execute(sql, (item_id,))
        connection.commit()

        flash("Testimonio eliminado correctamente ✅", "success")
    except Exception as err:
        print(f"ERROR DELETE TESTIMONIO: {err}")
        flash("Ocurrió un error al eliminar.", "error")
    finally:
        closeConnection(connection, cursor)

    return redirect(url_for("testimonios"))


@app.route("/editar-testimonio/<int:item_id>", methods=["GET", "POST"])
def editar_testimonio(item_id):
    testimonios_data = getData("testimonies")
    tsy_filter = [tsy for tsy in testimonios_data if tsy[0] == item_id]

    if not tsy_filter:
        flash("No se encontró el testimonio.", "error")
        return redirect(url_for("testimonios"))

    nombre = tsy_filter[0][1]
    mensaje = tsy_filter[0][2]

    if not session.get("autorizado"):
        return redirect(url_for("testimonios"))

    if request.method == "POST":
        nuevo_nombre = request.form.get("nombre", "").strip()
        nuevo_mensaje = request.form.get("mensaje", "").strip()

        if len(nuevo_nombre) == 0:
            nuevo_nombre = nombre

        if len(nuevo_mensaje) == 0:
            nuevo_mensaje = mensaje

        connection = dbConnection()

        if connection is None:
            flash("No se pudo conectar a la base de datos.", "error")
            return redirect(url_for("testimonios"))

        cursor = connection.cursor()
        try:
            sql = "UPDATE testimonies SET tsy_name = %s, tsy_msg = %s WHERE tsy_id = %s"
            cursor.execute(sql, (nuevo_nombre, nuevo_mensaje, item_id))
            connection.commit()

            flash("Testimonio actualizado correctamente ✅", "success")
            return redirect(url_for("testimonios"))
        except Exception as err:
            connection.rollback()
            print("Error editando testimonio:", err)
            flash("Error al editar testimonio", "error")
            return redirect(url_for("testimonios"))
        finally:
            closeConnection(connection, cursor)

    return render_template(
        "editar_testimonio.html",
        nombre=nombre,
        mensaje=mensaje,
        current_year=current_year
    )


# =========================
# RESULTADOS
# =========================

@app.route("/resultados", methods=["GET"])
def resultados():
    imagenes = getData("images")

    return render_template(
        "resultados.html",
        imagenes=imagenes,
        autorizado=session.get("autorizado"),
        current_year=current_year
    )


@app.route("/admin/galeria", methods=["GET", "POST"])
def admin_galeria():
    if not session.get("autorizado"):
        return redirect(url_for("admin"))

    imagenes = getData("images")

    if request.method == "POST":
        if "imagen" not in request.files:
            flash("No se envió ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        file = request.files["imagen"]

        if file.filename == "":
            flash("No seleccionaste ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        if file and allowed_file(file.filename):
            try:
                response = cloudinary.uploader.upload(file)
                secure_url = response["secure_url"]
            except Exception as err:
                print(f"ERROR CLOUDINARY: {err}")
                flash("Error al subir la imagen a Cloudinary.", "error")
                return redirect(url_for("admin_galeria"))

            connection = dbConnection()

            if connection is None:
                flash("No se pudo conectar a la base de datos.", "error")
                return redirect(url_for("admin_galeria"))

            cursor = connection.cursor()
            try:
                sql = "INSERT INTO images (img_url) VALUES (%s)"
                cursor.execute(sql, (secure_url,))
                connection.commit()

                flash("Imagen subida correctamente ✅", "success")
            except Exception as err:
                connection.rollback()
                print(f"ERROR INSERT IMAGE: {err}")
                flash("Ocurrió un error al guardar la imagen en la base.", "error")
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

    if connection is None:
        flash("No se pudo conectar a la base de datos.", "error")
        return redirect(url_for("admin_galeria"))

    cursor = connection.cursor()
    try:
        sql = "DELETE FROM images WHERE img_id = %s"
        cursor.execute(sql, (item_id,))
        connection.commit()

        flash("Imagen eliminada correctamente ✅", "success")
    except Exception as err:
        print(f"ERROR DELETE IMAGE: {err}")
        flash("Ocurrió un error al eliminar la imagen.", "error")
    finally:
        closeConnection(connection, cursor)

    return redirect(url_for("admin_galeria"))


# =========================
# FORMULARIO PAR-Q
# =========================

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
                recipients=[app.config["MAIL_USERNAME"]],
                html=html
            )
            mail.send(msg)
            flash("Formulario enviado correctamente ✅", "success")
        except Exception as e:
            print("Error enviando PAR-Q:", e)
            flash("Error al enviar el formulario ❌", "error")

        return redirect(url_for("parq"))

    return render_template("parq.html", current_year=current_year)


# =========================
# EJECUTAR
# =========================

if __name__ == "__main__":
    app.run(debug=True)