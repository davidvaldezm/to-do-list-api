"""Build two report pages plus screenshot annexes from verified evidence.

Run from repository root: python docs/build_report.py
Needs reportlab and Pillow. No AWS credentials or state are read by this script.
"""
import json
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)
FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Report", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("ReportBold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold")
NAVY = colors.HexColor("#142C45")
TEAL = colors.HexColor("#087D85")
GRAY = colors.HexColor("#526373")
PALE = colors.HexColor("#EDF4F7")
WIDTH, HEIGHT = 612, 792
MARGIN = 42
CONTENT = WIDTH - MARGIN * 2
DATA = json.loads((EVIDENCE / "validation.json").read_text(encoding="utf-8"))

canvas = Canvas(str(OUT / "reporte-practica4-david-valdez.pdf"), pagesize=(WIDTH, HEIGHT))
canvas.setTitle("Práctica 4 - To-Do List: CI/CD y observabilidad")
canvas.setAuthor("David Valdez Martinez")


def paragraph(text, y, size=10, leading=14, color=NAVY, x=MARGIN, width=CONTENT):
    style = ParagraphStyle("body", fontName="Report", fontSize=size, leading=leading,
                           textColor=color, alignment=TA_LEFT, spaceAfter=0)
    item = Paragraph(text, style)
    _, height = item.wrap(width, HEIGHT)
    item.drawOn(canvas, x, y - height)
    return y - height - 8


def heading(text, y):
    return paragraph(text, y, size=12, leading=16, color=TEAL) - 2


def footer(label, width=WIDTH):
    canvas.setStrokeColor(colors.HexColor("#CDDAE1"))
    canvas.line(MARGIN, 32, width - MARGIN, 32)
    canvas.setFillColor(GRAY)
    canvas.setFont("Report", 8)
    canvas.drawString(MARGIN, 19, "David Valdez Martinez | Desarrollo en la nube | 19 de noviembre de 2026")
    canvas.drawRightString(width - MARGIN, 19, label)


def box(x, y, w, h, title, detail, fill=PALE):
    canvas.setFillColor(fill)
    canvas.setStrokeColor(colors.HexColor("#B9CDD7"))
    canvas.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    paragraph(f"<b>{title}</b>", y + h - 9, size=8.8, leading=11, x=x + 8, width=w - 16)
    paragraph(detail, y + h - 24, size=7.7, leading=10, color=GRAY, x=x + 8, width=w - 16)


def arrow(x1, y1, x2, y2):
    from math import atan2, cos, sin
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(1.2)
    canvas.line(x1, y1, x2, y2)
    angle = atan2(y2 - y1, x2 - x1)
    for offset in [-0.45, 0.45]:
        canvas.line(x2, y2, x2 - 6 * cos(angle + offset), y2 - 6 * sin(angle + offset))


y = paragraph("<b>To-Do List en AWS</b>", HEIGHT - 38, size=23, leading=28)
y = paragraph("Práctica 4 | CI/CD + observabilidad", y, size=12, leading=16, color=TEAL)
y = paragraph("<b>David Valdez Martinez</b> · Desarrollo en la nube · 19 de noviembre de 2026", y,
              size=9.2, leading=13, color=GRAY) - 4
y = paragraph(
    "La API gestiona tareas con FastAPI y las persiste en MySQL de Amazon RDS. "
    "Expone GET/POST /tasks, PATCH para completar tareas, GET /version y GET /health. "
    "El health check consulta realmente la base de datos y devuelve versión y timestamp UTC; "
    "responde HTTP 503 cuando RDS no esta disponible.", y)
y = heading("Arquitectura implementada", y)
diagram_top = y
bx = [42, 230, 418]
row1 = y - 48
row2 = y - 124
box(bx[0], row1, 152, 46, "GitHub Actions", "PR + CI · tag · release ZIP")
box(bx[1], row1, 152, 46, "EC2 / FastAPI", "SSM deploy · systemd :8000")
box(bx[2], row1, 152, 46, "RDS MySQL", "Privado · TLS · SG de la API")
arrow(194, row1 + 24, 230, row1 + 24)
arrow(382, row1 + 24, 418, row1 + 24)
box(bx[0], row2, 152, 50, "Terraform + S3", "Estado remoto cifrado y versionado")
box(bx[1], row2, 152, 50, "Secrets Manager", "Credenciales leidas en runtime")
box(bx[2], row2, 152, 50, "CloudWatch + SNS", "3 métricas · alarmas · correo")
arrow(118, row2 + 50, 266, row1)
arrow(306, row2 + 50, 306, row1)
arrow(370, row1, 469, row2 + 50)
y = row2 - 13
y = paragraph("Terraform crea EC2, su Security Group y Key Pair, RDS y los recursos de observabilidad. "
              "La instancia usa LabInstanceProfile; RDS solo acepta tráfico de la API. "
              "El bucket se declara mediante una pila CloudFormation administrada por Terraform "
              "para respetar las restricciones de Learner Lab.", y, size=9.4, leading=13)
y = heading("1. Terraform frente a provisionar a mano; scp y user_data", y)
y = paragraph(
    "La ventaja concreta fue reconstruir recursos y sus relaciones desde la misma configuración. "
    "Terraform ordenó la creación de RDS, el secret y EC2, y limitó el acceso MySQL al Security Group "
    "correcto. Repetir esos enlaces y reglas a mano habría requerido revisar varios servicios "
    "y copiar identificadores. El estado en S3 conserva lo administrado entre ejecuciones.", y)
y = paragraph(
    "scp copia archivos a una máquina existente y exige conexión, llave y una intervención posterior; "
    "no instala dependencias ni garantiza que el servidor arranque. user_data se ejecuta durante "
    "el primer arranque: clona el repositorio, instala Python y dependencias y habilita systemd. "
    "Para versiones posteriores, el pipeline descarga un release por SSM y verifica su SHA256.", y)
y = heading("2. Pasos manuales y riesgos eliminados", y)
y = paragraph(
    "Dejé de ejecutar pruebas por separado, comprimir archivos, copiarlos al servidor y reiniciar "
    "el proceso a mano. Un PR requiere pruebas y validación Terraform; una etiqueta publica "
    "el ZIP del release y el deploy instala esa versión y comprueba /health y /version. "
    "Antes podía omitir pruebas, copiar una revisión equivocada o dejar el servicio detenido. "
    "El deploy restaura la versión previa si su verificacion de salud falla.", y)
if y < 44:
    raise ValueError(f"Report page one overflow: {y}")
footer("1 / 2")
canvas.showPage()

y = paragraph("<b>Observabilidad y validación</b>", HEIGHT - 42, size=20, leading=25)
y = paragraph("Tres métricas, tres alarmas y un dashboard provisionados por Terraform.", y,
              size=10, leading=14, color=GRAY) - 5

for title, detail in [
    ("CPUUtilization · nativa de EC2", "Average &gt;80% en 2 de 2 periodos de 300 s. "
     "Diez minutos filtran picos breves y detectan saturación sostenida. Revisaría procesos, "
     "tráfico y capacidad antes de optimizar o aumentar la instancia."),
    ("RdsErrors · propia, boto3 put_metric_data", "Sum &gt;=1 en 1 periodo de 60 s. "
     "Una lectura o escritura fallida ya afecta el servicio, por eso busco detección rápida. "
     "Revisaría /health, estado de RDS, conectividad, Security Groups y acceso al secret."),
    ("PendingTasks · propia, boto3 put_metric_data", "Maximum &gt;10 en 2 de 2 periodos de 300 s. "
     "La elegí porque describe el trabajo que sigue pendiente; en esta app pequeña, más de diez "
     "durante dos ventanas sugiere acumulación. Revisaría tareas y completaría trabajo. "
     "El heartbeat consulta la base cada 60 s para mantener visible esta métrica."),
]:
    y = heading(title, y)
    y = paragraph(detail, y, size=9.8, leading=13.5) - 3

y = paragraph(
    "Las tres alarmas notifican ALARM y recuperación OK al mismo topic SNS. "
    f"Suscripción de correo: <b>{DATA['sns_status']}</b>. "
    "El dashboard permite correlacionar CPU, fallos de persistencia y pendientes. "
    "Los datos ausentes se tratan como no alarmantes para evitar ruido durante el apagado del lab; "
    "un workflow adicional consulta /health cada cinco minutos.", y)
y = heading("3. Incidente real: RDS detenido", y)
y = paragraph(
    "Una detención de RDS por mantenimiento o una pérdida de conectividad dispara RdsErrors. "
    "En la validación detuve la RDS de esta práctica: la API devolvio 503 y la alarma paso a ALARM "
    "por errores reales de conexión, sin forzar su estado. En el dashboard buscaría el aumento "
    "de errores y compararia CPU y pendientes para delimitar el problema.", y)
y = paragraph(
    "La acción fue iniciar RDS, esperar su estado available y repetir GET /tasks y /health. "
    "Se comprobó la recuperación de la conexión, la conservación de las tareas y el retorno "
    "de la alarma a OK. Si RDS ya estuviera disponible, revisaría primero reglas de red, "
    "logs del servicio y acceso de su rol al secret, sin exponer credenciales.", y)
y = heading("Resultados verificables y límites del laboratorio", y)
y = paragraph(
    f"<b>{DATA['unit_tests']} pruebas aprobadas</b> en CI y PR integrado con main protegida. "
    f"Release <b>{DATA['version']}</b> publicado con ZIP y SHA256; deploy exitoso por SSM y "
    "versión confirmada en el endpoint. Los workflows manuales de provisión y destrucción "
    "tienen ejecuciones exitosas. El estado permanece en S3 y no se subió al repositorio. "
    "Los anexos muestran las tres evidencias obligatorias y las ejecuciones de Actions.", y, size=9.6, leading=13)
y = paragraph(
    "Learner Lab usa credenciales temporales: al vencer deben renovarse los tres secrets de Actions. "
    "GitHub puede retrasar el cron. Tras recopilar evidencia se destruyeron los recursos de la "
    "aplicación para conservar presupuesto; el backend remoto se retuvo para volver a provisionar. "
    "El cron se desactiva tras destruir y se reactiva al provisionar.",
    y, size=9.1, leading=12.5, color=GRAY)
y = paragraph(
    '<b>Código y evidencias:</b> <link href="https://github.com/davidvaldezm/to-do-list-api" color="#087D85">'
    'github.com/davidvaldezm/to-do-list-api</link><br/>'
    '<b>Fuente técnica:</b> <link href="https://developer.hashicorp.com/terraform/language/backend/s3" color="#087D85">'
    'HashiCorp: backend S3</link> · '
    '<link href="https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricData.html" color="#087D85">'
    'AWS: PutMetricData</link>', y, size=8.5, leading=12)
if y < 44:
    raise ValueError(f"Report page two overflow: {y}")
footer("2 / 2")
canvas.showPage()

annexes = [
    ("Dashboard de CloudWatch (1/2)", "01-dashboard.jpg", "Captura original, parte superior: dashboard de AWS y CPU nativa de EC2.", (0, 0, 1264, 625)),
    ("Dashboard de CloudWatch (2/2)", "01-dashboard.jpg", "Continuación de la misma captura: errores de RDS durante la detención y tareas pendientes.", (0, 625, 1264, 1394)),
    ("Alarma por detención real de RDS", "02-rds-alarm.jpg", "La alarma RdsErrors en ALARM por errores de conexión; notificaciones conectadas a SNS.", None),
    ("tfstate remoto en Amazon S3", "03-remote-state.jpg", "Objeto application/terraform.tfstate en el bucket privado del backend remoto.", None),
    ("Ejecuciones de GitHub Actions", "04-actions.jpg", "Listado de workflows y ejecuciones recientes. Los enlaces de cada ejecución exitosa están en evidence/README.md.", None),
]
for index, (title, filename, caption, crop) in enumerate(annexes, 1):
    path = EVIDENCE / filename
    if not path.is_file():
        raise FileNotFoundError(path)
    canvas.setPageSize((792, 612))
    paragraph(f"<b>Anexo {index}. {title}</b>", 579, size=17, leading=22, width=708)
    paragraph(caption, 548, size=10, leading=14, color=GRAY, width=708)
    with Image.open(path) as image:
        if crop:
            image = image.crop(crop)
        image_width, image_height = image.size
        rendered_image = ImageReader(image.copy())
    scale = min(708 / image_width, 458 / image_height)
    w, h = image_width * scale, image_height * scale
    canvas.drawImage(rendered_image, (792 - w) / 2, 52 + (458 - h) / 2, width=w, height=h)
    footer(f"Anexo {index}", width=792)
    canvas.showPage()
canvas.save()
print(OUT / "reporte-practica4-david-valdez.pdf")
