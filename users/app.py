from flask import Flask, request, jsonify
import json
import os
import logging
import threading
import bcrypt
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "timbu1901")
USERS_FILE = os.environ.get("USERS_FILE", "users.json")
PORT = int(os.environ.get("PORT", 5001))

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [users] %(message)s",
    handlers=[
        logging.FileHandler("users.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("users")

# Lock para evitar corrupcao do arquivo JSON sob concorrencia
file_lock = threading.Lock()


# =========================
# SENHA (bcrypt)
# =========================
def hash_senha(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha, hash_armazenado):
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_armazenado.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


# =========================
# PERSISTENCIA
# =========================
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump([], f)


def carregar_usuarios():
    with file_lock:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def salvar_usuarios(usuarios):
    with file_lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)


# =========================
# JWT
# =========================
def verificar_token():
    auth = request.headers.get("Authorization")

    if not auth:
        return None

    try:
        token = auth.split(" ")[1]

        dados = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )

        return dados

    except Exception:
        return None


# =========================
# ROTAS
# =========================
@app.route("/")
def home():
    return jsonify({"msg": "API de usuarios funcionando"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/users/register", methods=["POST"])
def register():
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({"erro": "JSON invalido ou ausente"}), 400

    nome = dados.get("nome")
    email = dados.get("email")
    senha = dados.get("senha")

    if not nome or not email or not senha:
        return jsonify({
            "erro": "Campos 'nome', 'email' e 'senha' sao obrigatorios"
        }), 400

    usuarios = carregar_usuarios()

    if any(u["email"] == email for u in usuarios):
        return jsonify({"erro": "Email ja cadastrado"}), 409

    novo_id = max((u["id"] for u in usuarios), default=0) + 1

    novo_usuario = {
        "id": novo_id,
        "nome": nome,
        "email": email,
        # role NUNCA e aceita do cliente: todo cadastro nasce como "user".
        # Para criar um admin, ver README_execucao.md (promocao manual/seed).
        "role": "user",
        "senha": hash_senha(senha)
    }

    usuarios.append(novo_usuario)
    salvar_usuarios(usuarios)

    logger.info(f"Novo usuario registrado: id={novo_id} email={email}")

    return jsonify({"msg": "Usuario cadastrado", "id": novo_id}), 201


@app.route("/users/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({"erro": "JSON invalido ou ausente"}), 400

    email = dados.get("email")
    senha = dados.get("senha")

    if not email or not senha:
        return jsonify({
            "erro": "Campos 'email' e 'senha' sao obrigatorios"
        }), 400

    usuarios = carregar_usuarios()

    for usuario in usuarios:

        if usuario["email"] == email and verificar_senha(senha, usuario["senha"]):

            token = jwt.encode(
                {
                    "userId": usuario["id"],
                    "email": usuario["email"],
                    "role": usuario["role"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                SECRET_KEY,
                algorithm="HS256"
            )

            logger.info(f"Login bem-sucedido: email={email} userId={usuario['id']}")

            return jsonify({"token": token})

    logger.warning(f"Tentativa de login invalida para email={email}")

    return jsonify({"erro": "Login invalido"}), 401


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):

    usuario_token = verificar_token()

    if not usuario_token:
        return jsonify({"erro": "Token invalido ou ausente"}), 401

    # Usuario comum so pode ver o proprio perfil; admin pode ver qualquer um.
    if usuario_token["userId"] != user_id and usuario_token.get("role") != "admin":
        return jsonify({
            "erro": "Acesso negado: voce so pode visualizar o proprio perfil"
        }), 403

    usuarios = carregar_usuarios()

    for usuario in usuarios:
        if usuario["id"] == user_id:
            # Nunca retornar o hash da senha ao cliente.
            return jsonify({
                "id": usuario["id"],
                "nome": usuario["nome"],
                "email": usuario["email"],
                "role": usuario["role"]
            })

    return jsonify({"erro": "Usuario nao encontrado"}), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
