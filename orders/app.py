from flask import Flask, request, jsonify
import json
import os
import logging
import threading
import requests
import jwt

app = Flask(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "timbu1901")
ORDERS_FILE = os.environ.get("ORDERS_FILE", "orders.json")

# Servico de produtos usado para validar a existencia do produto.
PRODUCTS_URL = os.environ.get("PRODUCTS_URL", "http://products-primary:5002")

PORT = int(os.environ.get("PORT", 5003))

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [orders] %(message)s",
    handlers=[
        logging.FileHandler("orders.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("orders")

# Lock para evitar corrupcao do arquivo JSON sob concorrencia
file_lock = threading.Lock()

# Cria o arquivo se nao existir
if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w") as f:
        json.dump([], f)


def carregar_pedidos():
    with file_lock:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def salvar_pedidos(pedidos):
    with file_lock:
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(pedidos, f, indent=4, ensure_ascii=False)


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


def produto_existe(product_id):
    """Consulta o servico de produtos para validar a existencia do produto.

    Retorna (True, None) se existir, (False, status_http) caso contrario
    ou se o servico de produtos estiver indisponivel.
    """
    try:
        resposta = requests.get(
            f"{PRODUCTS_URL}/products/{product_id}",
            timeout=3
        )
    except Exception as e:
        logger.error(f"Erro ao consultar servico de produtos: {e}")
        return False, 503

    if resposta.status_code == 200:
        return True, None

    return False, 404


@app.route("/")
def home():
    return jsonify({"msg": "Servico de Pedidos Online"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# Criar pedido
@app.route("/orders", methods=["POST"])
def criar_pedido():

    usuario = verificar_token()

    if not usuario:
        return jsonify({"erro": "Token invalido ou ausente"}), 401

    dados = request.get_json(silent=True)

    if not dados or "productId" not in dados:
        return jsonify({"erro": "Campo 'productId' e obrigatorio"}), 400

    product_id = dados["productId"]

    existe, status_erro = produto_existe(product_id)

    if not existe:
        if status_erro == 503:
            return jsonify({
                "erro": "Servico de produtos indisponivel, nao foi possivel validar o pedido"
            }), 503

        return jsonify({"erro": "Produto nao encontrado"}), 404

    pedidos = carregar_pedidos()

    novo_pedido = {
        "id": max((p["id"] for p in pedidos), default=0) + 1,
        "userId": usuario["userId"],
        "productId": product_id
    }

    pedidos.append(novo_pedido)

    salvar_pedidos(pedidos)

    logger.info(f"Pedido criado: {novo_pedido}")

    return jsonify(novo_pedido), 201


# Listar pedidos de um usuário
@app.route("/orders/<int:user_id>", methods=["GET"])
def listar_pedidos(user_id):

    usuario = verificar_token()

    if not usuario:
        return jsonify({"erro": "Token invalido ou ausente"}), 401

    # Usuario comum so pode ver os proprios pedidos; admin pode ver de qualquer um.
    if usuario["userId"] != user_id and usuario.get("role") != "admin":
        return jsonify({
            "erro": "Acesso negado: voce so pode visualizar seus proprios pedidos"
        }), 403

    pedidos = carregar_pedidos()

    pedidos_usuario = [p for p in pedidos if p["userId"] == user_id]

    return jsonify(pedidos_usuario)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
