from flask import Flask, request, jsonify
import json
import os
import logging
import threading
import requests
import jwt

app = Flask(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "timbu1901")

# ROLE define se esta instancia e o "primary" (aceita escrita) ou
# "replica" (somente leitura + recebe replicacao do primary).
ROLE = os.environ.get("ROLE", "primary").lower()

# Arquivo de dados desta instancia (cada instancia tem o seu proprio).
DATA_FILE = os.environ.get("DATA_FILE", "products_primary.json")

# URL da instancia parceira (usado apenas pelo primary para replicar).
PEER_URL = os.environ.get("PEER_URL")

PORT = int(os.environ.get("PORT", 5002))

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [%(levelname)s] [products-{ROLE}] %(message)s",
    handlers=[
        logging.FileHandler("products.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("products")

# Lock para evitar corrupcao do arquivo JSON sob concorrencia
file_lock = threading.Lock()

# Cria o arquivo de dados caso nao exista
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def carregar_produtos():
    with file_lock:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def salvar_produtos(produtos):
    with file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(produtos, f, indent=4, ensure_ascii=False)


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


@app.route("/")
def home():
    return jsonify({"servico": "products", "role": ROLE})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "role": ROLE})


@app.route("/products", methods=["GET"])
def listar_produtos():
    return jsonify(carregar_produtos())


@app.route("/products/<int:product_id>", methods=["GET"])
def buscar_produto(product_id):

    produtos = carregar_produtos()

    for produto in produtos:
        if produto["id"] == product_id:
            return jsonify(produto)

    return jsonify({
        "erro": "Produto nao encontrado"
    }), 404


# =========================
# REPLICACAO (uso interno)
# =========================
@app.route("/internal/replicate", methods=["POST"])
def replicate():
    # So a replica aceita escrita por replicacao.
    if ROLE != "replica":
        return jsonify({"erro": "Apenas a replica aceita replicacao"}), 403

    dados = request.get_json(silent=True)

    if not dados or "produtos" not in dados:
        return jsonify({"erro": "Payload de replicacao invalido"}), 400

    salvar_produtos(dados["produtos"])

    logger.info("Replicacao recebida e aplicada com sucesso")

    return jsonify({"status": "ok"}), 200


@app.route("/products", methods=["POST"])
def criar_produto():

    # Apenas a instancia primaria aceita escrita de clientes.
    if ROLE != "primary":
        return jsonify({
            "erro": "Esta instancia e somente leitura (replica). Use o primario."
        }), 403

    usuario = verificar_token()

    if not usuario:
        return jsonify({"erro": "Token invalido ou ausente"}), 401

    if usuario.get("role") != "admin":
        return jsonify({
            "erro": "Apenas administradores podem criar produtos"
        }), 403

    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({"erro": "JSON invalido ou ausente"}), 400

    nome = dados.get("nome")
    preco = dados.get("preco")

    if not nome or preco is None:
        return jsonify({
            "erro": "Campos 'nome' e 'preco' sao obrigatorios"
        }), 400

    produtos = carregar_produtos()

    novo_produto = {
        "id": max((p["id"] for p in produtos), default=0) + 1,
        "nome": nome,
        "preco": preco
    }

    produtos_atualizados = produtos + [novo_produto]

    # Replicacao sincrona obrigatoria: so confirma a escrita se a
    # replica tambem confirmar (consistencia forte: tudo ou nada).
    if PEER_URL:
        try:
            resposta = requests.post(
                f"{PEER_URL}/internal/replicate",
                json={"produtos": produtos_atualizados},
                timeout=3
            )

            if resposta.status_code != 200:
                raise RuntimeError(f"replica retornou status {resposta.status_code}")

        except Exception as e:
            logger.error(f"Falha ao replicar produto para a replica: {e}")
            return jsonify({
                "erro": "Falha ao replicar para a instancia secundaria. "
                        "Escrita abortada para preservar consistencia."
            }), 503

    salvar_produtos(produtos_atualizados)

    logger.info(f"Produto criado e replicado com sucesso: {novo_produto}")

    return jsonify(novo_produto), 201


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
