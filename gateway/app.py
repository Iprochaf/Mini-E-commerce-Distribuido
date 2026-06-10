from flask import Flask, request, jsonify
import requests
import threading
import time

app = Flask(__name__)

# Endereços dos microsserviços
SERVICES = {
    "users": "http://localhost:5001",
    "products": "http://localhost:5002",
    "orders": "http://localhost:5003"
}

# Status dos serviços
STATUS = {
    "users": True,
    "products": True,
    "orders": True
}


# Heartbeat
def heartbeat():

    while True:

        for nome, url in SERVICES.items():

            try:

                requests.get(
                    f"{url}/health",
                    timeout=2
                )

                if STATUS[nome] == False:
                    print(
                        f"[RECUPERADO] {nome}"
                    )

                STATUS[nome] = True

            except:

                if STATUS[nome] == True:
                    print(
                        f"[FALHA] {nome}"
                    )

                STATUS[nome] = False

        time.sleep(5)


# Inicia heartbeat em background
threading.Thread(
    target=heartbeat,
    daemon=True
).start()


@app.route("/")
def home():

    return jsonify({
        "gateway": "online",
        "services": STATUS
    })


# =========================
# USERS
# =========================

@app.route("/users/register", methods=["POST"])
def register():

    resposta = requests.post(
        f"{SERVICES['users']}/users/register",
        json=request.json
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


@app.route("/users/login", methods=["POST"])
def login():

    resposta = requests.post(
        f"{SERVICES['users']}/users/login",
        json=request.json
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):

    if not STATUS["users"]:
        return jsonify({
            "erro": "Servico de usuarios indisponivel"
        }), 503

    headers = {
        "Authorization":
        request.headers.get("Authorization")
    }

    resposta = requests.get(
        f"{SERVICES['users']}/users/{user_id}",
        headers=headers
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


# =========================
# PRODUCTS
# =========================

@app.route("/products", methods=["GET"])
def listar_produtos():

    if not STATUS["products"]:
        return jsonify({
            "erro": "Servico de produtos indisponivel"
        }), 503

    resposta = requests.get(
        f"{SERVICES['products']}/products"
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


@app.route("/products/<int:product_id>", methods=["GET"])
def buscar_produto(product_id):

    if not STATUS["products"]:
        return jsonify({
            "erro": "Servico de produtos indisponivel"
        }), 503

    resposta = requests.get(
        f"{SERVICES['products']}/products/{product_id}"
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


@app.route("/products", methods=["POST"])
def criar_produto():

    if not STATUS["products"]:
        return jsonify({
            "erro": "Servico de produtos indisponivel"
        }), 503

    headers = {
        "Authorization":
        request.headers.get("Authorization")
    }

    resposta = requests.post(
        f"{SERVICES['products']}/products",
        json=request.json,
        headers=headers
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


# =========================
# ORDERS
# =========================

@app.route("/orders", methods=["POST"])
def criar_pedido():

    if not STATUS["orders"]:
        return jsonify({
            "erro": "Servico de pedidos indisponivel"
        }), 503

    headers = {
        "Authorization":
        request.headers.get("Authorization")
    }

    resposta = requests.post(
        f"{SERVICES['orders']}/orders",
        json=request.json,
        headers=headers
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


@app.route("/orders/<int:user_id>", methods=["GET"])
def listar_pedidos(user_id):

    if not STATUS["orders"]:
        return jsonify({
            "erro": "Servico de pedidos indisponivel"
        }), 503

    headers = {
        "Authorization":
        request.headers.get("Authorization")
    }

    resposta = requests.get(
        f"{SERVICES['orders']}/orders/{user_id}",
        headers=headers
    )

    return jsonify(
        resposta.json()
    ), resposta.status_code


# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )