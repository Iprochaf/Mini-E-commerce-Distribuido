from flask import Flask, request, jsonify
import requests
import threading
import time
import os
import logging

app = Flask(__name__)

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [gateway] %(message)s",
    handlers=[
        logging.FileHandler("gateway.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gateway")

# =========================
# ENDERECOS DOS MICROSSERVICOS
# =========================
SERVICES = {
    "users": os.environ.get("USERS_URL", "http://users:5001"),
    "products_primary": os.environ.get("PRODUCTS_PRIMARY_URL", "http://products-primary:5002"),
    "products_replica": os.environ.get("PRODUCTS_REPLICA_URL", "http://products-replica:5002"),
    "orders": os.environ.get("ORDERS_URL", "http://orders:5003"),
}

HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "5"))

# Numero de falhas consecutivas necessarias para marcar um servico como indisponivel.
FAILURE_THRESHOLD = 2

# Status (disponibilidade) de cada servico
STATUS = {nome: True for nome in SERVICES}

# Contador de falhas consecutivas por servico
FAIL_COUNT = {nome: 0 for nome in SERVICES}


# =========================
# HEARTBEAT
# =========================
def heartbeat():

    while True:

        for nome, url in SERVICES.items():

            try:
                requests.get(f"{url}/health", timeout=2)

                if not STATUS[nome]:
                    logger.info(f"[RECUPERADO] Servico '{nome}' voltou a responder")

                STATUS[nome] = True
                FAIL_COUNT[nome] = 0

            except Exception:

                FAIL_COUNT[nome] += 1

                if FAIL_COUNT[nome] >= FAILURE_THRESHOLD and STATUS[nome]:
                    logger.warning(
                        f"[FALHA] Servico '{nome}' marcado como indisponivel "
                        f"apos {FAIL_COUNT[nome]} falhas consecutivas"
                    )
                    STATUS[nome] = False

        time.sleep(HEARTBEAT_INTERVAL)


# Inicia heartbeat em background
threading.Thread(
    target=heartbeat,
    daemon=True
).start()


# =========================
# ROUND-ROBIN (PRODUCTS)
# =========================
products_rr_index = 0
products_rr_lock = threading.Lock()

PRODUCTS_INSTANCES = ["products_primary", "products_replica"]


def escolher_instancia_produtos():
    """Escolhe a proxima instancia de products em round-robin real,
    pulando instancias marcadas como indisponiveis (failover)."""

    global products_rr_index

    with products_rr_lock:
        for i in range(len(PRODUCTS_INSTANCES)):
            idx = (products_rr_index + i) % len(PRODUCTS_INSTANCES)
            nome = PRODUCTS_INSTANCES[idx]

            if STATUS[nome]:
                products_rr_index = (idx + 1) % len(PRODUCTS_INSTANCES)
                return nome, SERVICES[nome]

    return None, None


def repassar(metodo, url, **kwargs):
    """Repassa uma requisicao ao microsservico, tratando falhas de conexao."""
    try:
        resposta = requests.request(metodo, url, timeout=5, **kwargs)
        return jsonify(resposta.json()), resposta.status_code
    except Exception as e:
        logger.error(f"Erro ao comunicar com {url}: {e}")
        return jsonify({"erro": "Servico indisponivel"}), 503


@app.route("/")
def home():
    return jsonify({
        "gateway": "online",
        "services": STATUS
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# =========================
# USERS
# =========================

@app.route("/users/register", methods=["POST"])
def register():

    if not STATUS["users"]:
        return jsonify({"erro": "Servico de usuarios indisponivel"}), 503

    return repassar(
        "POST",
        f"{SERVICES['users']}/users/register",
        json=request.get_json(silent=True)
    )


@app.route("/users/login", methods=["POST"])
def login():

    if not STATUS["users"]:
        return jsonify({"erro": "Servico de usuarios indisponivel"}), 503

    return repassar(
        "POST",
        f"{SERVICES['users']}/users/login",
        json=request.get_json(silent=True)
    )


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):

    if not STATUS["users"]:
        return jsonify({"erro": "Servico de usuarios indisponivel"}), 503

    headers = {"Authorization": request.headers.get("Authorization", "")}

    return repassar(
        "GET",
        f"{SERVICES['users']}/users/{user_id}",
        headers=headers
    )


# =========================
# PRODUCTS
# =========================

@app.route("/products", methods=["GET"])
def listar_produtos():

    nome, url = escolher_instancia_produtos()

    if not url:
        return jsonify({"erro": "Servico de produtos indisponivel"}), 503

    return repassar("GET", f"{url}/products")


@app.route("/products/<int:product_id>", methods=["GET"])
def buscar_produto(product_id):

    nome, url = escolher_instancia_produtos()

    if not url:
        return jsonify({"erro": "Servico de produtos indisponivel"}), 503

    return repassar("GET", f"{url}/products/{product_id}")


@app.route("/products", methods=["POST"])
def criar_produto():

    # Escrita sempre vai para a instancia primaria, que se encarrega
    # de replicar de forma sincrona para a replica.
    if not STATUS["products_primary"]:
        return jsonify({"erro": "Servico de produtos (primario) indisponivel"}), 503

    headers = {"Authorization": request.headers.get("Authorization", "")}

    return repassar(
        "POST",
        f"{SERVICES['products_primary']}/products",
        json=request.get_json(silent=True),
        headers=headers
    )


# =========================
# ORDERS
# =========================

@app.route("/orders", methods=["POST"])
def criar_pedido():

    if not STATUS["orders"]:
        return jsonify({"erro": "Servico de pedidos indisponivel"}), 503

    headers = {"Authorization": request.headers.get("Authorization", "")}

    return repassar(
        "POST",
        f"{SERVICES['orders']}/orders",
        json=request.get_json(silent=True),
        headers=headers
    )


@app.route("/orders/<int:user_id>", methods=["GET"])
def listar_pedidos(user_id):

    if not STATUS["orders"]:
        return jsonify({"erro": "Servico de pedidos indisponivel"}), 503

    headers = {"Authorization": request.headers.get("Authorization", "")}

    return repassar(
        "GET",
        f"{SERVICES['orders']}/orders/{user_id}",
        headers=headers
    )


# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
