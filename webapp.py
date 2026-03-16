import os
import tempfile
import threading
from dataclasses import asdict
from flask import Flask, render_template_string, request

from main import normalize_number, run_automation


app = Flask(__name__)
STATUS = {
    "running": False,
    "logs": [],
    "results": [],
    "image_path": "",
    "last_error": "",
}


HTML = """<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="utf-8">
    <title>DispaZap</title>
    <link
      rel="icon"
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/svgs/brands/whatsapp.svg"
      type="image/svg+xml"
    >
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Fraunces:wght@600;700&display=swap");
    </style>
    <link
      rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"
      referrerpolicy="no-referrer"
    >
    <style>
      :root {
        --bg: #f5f4f0;
        --bg-2: #f0e9df;
        --card: #ffffff;
        --text: #1d1d1f;
        --muted: #5a5a65;
        --accent: #f97316;
        --accent-2: #10b981;
        --border: #e3ded6;
        --shadow: 0 12px 30px rgba(0, 0, 0, 0.08);
      }
      body.dark {
        --bg: #0f1115;
        --bg-2: #141821;
        --card: #161b22;
        --text: #f0f3f6;
        --muted: #9aa4b2;
        --accent: #f97316;
        --accent-2: #22c55e;
        --border: #262c36;
        --shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Space Grotesk", "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(1200px 600px at 10% -10%, #ffd9b3, transparent 60%),
          radial-gradient(900px 500px at 90% 0%, #d4f8e8, transparent 55%),
          var(--bg);
        min-height: 100vh;
      }
      body.dark {
        background:
          radial-gradient(900px 500px at 10% -10%, rgba(249, 115, 22, 0.25), transparent 60%),
          radial-gradient(900px 500px at 90% 0%, rgba(16, 185, 129, 0.2), transparent 55%),
          var(--bg);
      }
      header {
        padding: 28px 20px 8px;
        text-align: center;
      }
      .title {
        font-family: "Fraunces", serif;
        font-size: clamp(28px, 5vw, 40px);
        letter-spacing: 0.5px;
        margin: 0;
      }
      .title i {
        color: var(--accent-2);
        margin-right: 10px;
      }
      .subtitle {
        margin: 6px 0 0;
        color: var(--muted);
        font-size: 14px;
      }
      .container {
        max-width: 1050px;
        margin: 0 auto;
        padding: 16px 20px 32px;
      }
      .toolbar {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        margin-bottom: 14px;
      }
      .toggle {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 1px solid var(--border);
        background: var(--card);
        color: var(--text);
        padding: 8px 12px;
        border-radius: 999px;
        cursor: pointer;
        box-shadow: var(--shadow);
      }
      .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 18px;
        box-shadow: var(--shadow);
      }
      label { display: block; margin-top: 14px; font-weight: 600; }
      textarea, input[type="text"], input[type="file"] {
        width: 100%;
        margin-top: 8px;
        padding: 12px 12px;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: transparent;
        color: var(--text);
        font-size: 14px;
      }
      textarea { height: 160px; resize: vertical; }
      .actions {
        display: flex;
        gap: 12px;
        margin-top: 16px;
        flex-wrap: wrap;
      }
      button {
        padding: 10px 18px;
        border-radius: 10px;
        border: none;
        background: var(--accent);
        color: #0b0b0b;
        font-weight: 700;
        cursor: pointer;
      }
      button[disabled] {
        opacity: 0.6;
        cursor: not-allowed;
      }
      .status-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-top: 18px;
      }
      .log {
        background: var(--bg-2);
        padding: 12px;
        border-radius: 12px;
        border: 1px solid var(--border);
        white-space: pre-wrap;
        min-height: 150px;
      }
      @media (max-width: 860px) {
        .status-grid { grid-template-columns: 1fr; }
        .toolbar { justify-content: center; }
      }
    </style>
    {% if running %}
    <meta http-equiv="refresh" content="3">
    {% endif %}
  </head>
  <body>
    <header>
      <h1 class="title"><i class="fa-brands fa-whatsapp"></i> DispaZap</h1>
      <p class="subtitle">Automacao local para envio com WhatsApp Web</p>
    </header>
    <div class="container">
      <div class="toolbar">
        <button class="toggle" type="button" id="themeToggle">
          <span>Modo escuro</span>
        </button>
      </div>
      <div class="card">
        <form method="post" enctype="multipart/form-data">
          <label>Numeros (um por linha ou separados por virgula)</label>
          <textarea name="numbers" required>{{ numbers }}</textarea>
          <label>Mensagem (aceita quebras de linha)</label>
          <textarea name="message" required>{{ message }}</textarea>
          <label>Imagem (opcional)</label>
          <input type="file" name="image" accept="image/*">
          <div class="actions">
            <button type="submit" {% if running %}disabled{% endif %}>Iniciar</button>
          </div>
        </form>
      </div>

      <div class="status-grid">
        <div>
          <h3>Status</h3>
          <div class="log">{{ logs }}</div>
        </div>
        <div>
          <h3>Resultados</h3>
          <div class="log">{{ results }}</div>
        </div>
        <div>
          <h3>Numeros nao encontrados</h3>
          <div class="log">{{ not_found }}</div>
        </div>
      </div>
    </div>
    <script>
      const toggle = document.getElementById("themeToggle");
      const stored = localStorage.getItem("dispwhatsapp-theme");
      if (stored === "light") {
        document.body.classList.remove("dark");
      } else {
        document.body.classList.add("dark");
      }
      toggle.addEventListener("click", () => {
        document.body.classList.toggle("dark");
        const mode = document.body.classList.contains("dark") ? "dark" : "light";
        localStorage.setItem("dispwhatsapp-theme", mode);
      });
    </script>
  </body>
</html>
"""


def parse_numbers(raw):
    numbers = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        for part in parts:
            digits = normalize_number(part)
            if digits:
                numbers.append(digits)
    return numbers


def log_append(message):
    STATUS["logs"].append(message)


def run_in_background(numbers, message):
    STATUS["running"] = True
    STATUS["logs"] = []
    STATUS["results"] = []
    STATUS["last_error"] = ""
    log_append("Processo iniciado.")

    try:
        results = run_automation(
            numbers, message, log_callback=log_append, image_path=STATUS["image_path"]
        )
        STATUS["results"] = [asdict(r) for r in results]
        if results and all(r.sent for r in results):
            log_append("Todos os envios foram realizados com sucesso.")
        elif results:
            log_append("Alguns envios falharam. Verifique os resultados.")
    except Exception as exc:
        STATUS["last_error"] = str(exc)
        log_append(f"Erro inesperado: {exc}")
    finally:
        STATUS["running"] = False


@app.route("/", methods=["GET", "POST"])
def index():
    numbers_text = ""
    message = ""
    if request.method == "POST" and not STATUS["running"]:
        numbers_text = request.form.get("numbers", "")
        message = request.form.get("message", "")
        image_file = request.files.get("image")
        numbers = parse_numbers(numbers_text)
        if numbers and message.strip():
            if image_file and image_file.filename:
                if STATUS["image_path"] and os.path.exists(STATUS["image_path"]):
                    os.remove(STATUS["image_path"])
                _, ext = os.path.splitext(image_file.filename)
                if not ext:
                    ext = ".png"
                fd, path = tempfile.mkstemp(prefix="wa_image_", suffix=ext)
                os.close(fd)
                image_file.save(path)
                STATUS["image_path"] = path
            else:
                STATUS["image_path"] = ""
            thread = threading.Thread(
                target=run_in_background, args=(numbers, message), daemon=True
            )
            thread.start()

    logs = "\n".join(STATUS["logs"]) or "Aguardando..."
    results_lines = []
    not_found_lines = []
    for r in STATUS["results"]:
        if r.get("sent"):
            results_lines.append(f"{r['number']}: enviado")
        else:
            reason = r.get("error") or "nao enviado"
            results_lines.append(f"{r['number']}: {reason}")
            if "nao encontrado" in reason:
                not_found_lines.append(r["number"])
    results = "\n".join(results_lines)
    if not results:
        results = "Sem resultados."
    not_found = "\n".join(not_found_lines) or "Sem numeros nao encontrados."
    return render_template_string(
        HTML,
        numbers=numbers_text,
        message=message,
        logs=logs,
        results=results,
        not_found=not_found,
        running=STATUS["running"],
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
