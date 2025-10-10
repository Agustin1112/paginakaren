import os
import json
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Configuración de subida
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Configuración de Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Configuración de correo
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

# ========= PÁGINAS PRINCIPALES =========

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/services')
def services():
    return render_template("services.html")

@app.route('/contact', methods=["GET", "POST"])
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
    return render_template("contact.html")

# ========= ADMIN SIMPLE =========

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        clave = request.form.get("clave")
        if clave == os.getenv("ADMIN_KEY"):
            session["autorizado"] = True
            flash("Acceso autorizado ✅", "success")
            return redirect(url_for("home"))
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
    try:
        with open("testimonios.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    return render_template("testimonios.html", testimonios=data, autorizado=session.get("autorizado"))

@app.route("/agregar-testimonio", methods=["GET", "POST"])
def agregar_testimonio():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        mensaje = request.form.get("mensaje")
        if nombre and mensaje:
            try:
                with open("testimonios.json", "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data.append({"nombre": nombre, "mensaje": mensaje})
                    f.seek(0)
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except FileNotFoundError:
                with open("testimonios.json", "w", encoding="utf-8") as f:
                    json.dump([{"nombre": nombre, "mensaje": mensaje}], f, ensure_ascii=False, indent=2)
            flash("Gracias por compartir tu testimonio ❤️", "success")
            return redirect(url_for("testimonios"))
        else:
            flash("Por favor, completá todos los campos.", "error")
    return render_template("agregar_testimonio.html")

@app.route("/eliminar-testimonio/<int:index>", methods=["POST"])
def eliminar_testimonio(index):
    clave = request.form.get("clave")
    if clave != os.getenv("ADMIN_KEY"):
        flash("Clave incorrecta ❌", "error")
        return redirect(url_for("testimonios"))
    try:
        with open("testimonios.json", "r+", encoding="utf-8") as f:
            data = json.load(f)
            if 0 <= index < len(data):
                data.pop(index)
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)
                flash("Testimonio eliminado correctamente ✅", "success")
    except Exception as e:
        print("Error eliminando testimonio:", e)
        flash("Ocurrió un error al eliminar.", "error")
    return redirect(url_for("testimonios"))

@app.route("/editar-testimonio/<int:index>", methods=["GET", "POST"])
def editar_testimonio(index):
    try:
        with open("testimonios.json", "r+", encoding="utf-8") as f:
            data = json.load(f)
            if index < 0 or index >= len(data):
                flash("Testimonio no encontrado.", "error")
                return redirect(url_for("testimonios"))
            if request.method == "POST":
                data[index]["nombre"] = request.form.get("nombre")
                data[index]["mensaje"] = request.form.get("mensaje")
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)
                flash("Testimonio actualizado correctamente ✅", "success")
                return redirect(url_for("testimonios"))
            return render_template("editar_testimonio.html", testimonio=data[index])
    except Exception as e:
        print("Error editando testimonio:", e)
        flash("Error al editar testimonio", "error")
        return redirect(url_for("testimonios"))

# ========= RESULTADOS =========

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/resultados")
def resultados():
    try:
        with open("resultados.json", "r", encoding="utf-8") as f:
            imagenes = json.load(f)
    except FileNotFoundError:
        imagenes = []
    return render_template("resultados.html", imagenes=imagenes, autorizado=session.get("autorizado"))

@app.route("/admin/galeria", methods=["GET", "POST"])
def admin_galeria():
    if not session.get("autorizado"):
        return redirect(url_for("admin"))
    try:
        with open("resultados.json", "r", encoding="utf-8") as f:
            imagenes = json.load(f)
    except FileNotFoundError:
        imagenes = []

    if request.method == "POST":
        if 'imagen' not in request.files:
            flash("No se envió ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        file = request.files["imagen"]
        if file.filename == '':
            flash("No seleccionaste ninguna imagen.", "error")
            return redirect(url_for("admin_galeria"))

        if file and allowed_file(file.filename):
            try:
                upload_result = cloudinary.uploader.upload(file)
                ruta_web = upload_result.get("secure_url")
                imagenes.append(ruta_web)
                with open("resultados.json", "w", encoding="utf-8") as f:
                    json.dump(imagenes, f, ensure_ascii=False, indent=2)
                flash("Imagen subida correctamente ✅", "success")
            except Exception as e:
                print("Error al subir a Cloudinary:", e)
                flash("Ocurrió un error al subir la imagen.", "error")
            return redirect(url_for("admin_galeria"))
        else:
            flash("Formato no permitido. Solo PNG, JPG, JPEG y GIF.", "error")

    return render_template("admin_galeria.html", imagenes=imagenes)

@app.route("/admin/galeria/eliminar/<int:index>", methods=["POST"])
def eliminar_resultado(index):
    if not session.get("autorizado"):
        return redirect(url_for("admin"))
    try:
        with open("resultados.json", "r+", encoding="utf-8") as f:
            imagenes = json.load(f)
            if 0 <= index < len(imagenes):
                imagenes.pop(index)
                f.seek(0)
                f.truncate()
                json.dump(imagenes, f, ensure_ascii=False, indent=2)
                flash("Imagen eliminada correctamente ✅", "success")
    except Exception as e:
        print("Error eliminando imagen:", e)
        flash("Ocurrió un error al eliminar la imagen.", "error")
    return redirect(url_for("admin_galeria"))

@app.route("/faq")
def faq():
    return render_template("faq.html")

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
