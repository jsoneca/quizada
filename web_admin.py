from flask import Flask, render_template_string, request, redirect, url_for
import json
import os

app = Flask(__name__)

QUIZ_FILE = "quizzes.json"

# Carregar perguntas
def carregar_quizzes():
    if not os.path.exists(QUIZ_FILE):
        with open(QUIZ_FILE, "w") as f:
            json.dump([], f)
    with open(QUIZ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Salvar perguntas
def salvar_quizzes(quizzes):
    with open(QUIZ_FILE, "w", encoding="utf-8") as f:
        json.dump(quizzes, f, indent=4, ensure_ascii=False)

# Página inicial
@app.route("/")
def index():
    quizzes = carregar_quizzes()
    return render_template_string("""
    <html>
    <head>
        <title>Gerenciar Quizzes</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f6f6f6; }
            h1 { color: #333; }
            form, .quiz-list { background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px #ccc; }
            .quiz-item { margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #eee; }
            input, textarea { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 6px; }
            button { background: #007bff; color: #fff; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .delete { background: red; }
        </style>
    </head>
    <body>
        <h1>🧩 Gerenciador de Quizzes</h1>
        <form action="/add" method="post">
            <label>Pergunta:</label><br>
            <textarea name="pergunta" required></textarea><br>
            <label>Opções (separe por vírgula):</label><br>
            <input type="text" name="opcoes" required><br>
            <label>Resposta correta (número da opção, começando em 0):</label><br>
            <input type="number" name="correta" min="0" required><br><br>
            <button type="submit">Adicionar Quiz</button>
        </form>

        <h2>Quizzes Existentes</h2>
        <div class="quiz-list">
        {% for q in quizzes %}
            <div class="quiz-item">
                <b>{{ loop.index }}. {{ q.pergunta }}</b><br>
                <small>Opções: {{ q.opcoes }}</small><br>
                <small>Correta: {{ q.correta }}</small><br><br>
                <form action="/delete/{{ loop.index0 }}" method="post">
                    <button class="delete">Excluir</button>
                </form>
            </div>
        {% else %}
            <p>Nenhum quiz cadastrado ainda.</p>
        {% endfor %}
        </div>
    </body>
    </html>
    """, quizzes=quizzes)

# Adicionar quiz
@app.route("/add", methods=["POST"])
def add_quiz():
    quizzes = carregar_quizzes()
    pergunta = request.form["pergunta"]
    opcoes = [x.strip() for x in request.form["opcoes"].split(",")]
    correta = int(request.form["correta"])
    quizzes.append({"pergunta": pergunta, "opcoes": opcoes, "correta": correta})
    salvar_quizzes(quizzes)
    return redirect(url_for("index"))

# Excluir quiz
@app.route("/delete/<int:quiz_id>", methods=["POST"])
def delete_quiz(quiz_id):
    quizzes = carregar_quizzes()
    if 0 <= quiz_id < len(quizzes):
        quizzes.pop(quiz_id)
        salvar_quizzes(quizzes)
    return redirect(url_for("index"))

# Rodar servidor Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
