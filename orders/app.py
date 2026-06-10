from flask import Flask, request, jsonify
import json
import os
import jwt

app = Flask(__name__)

SECRET_KEY = "senha123"
ORDERS_FILE = "orders.json"

# Cria o arquivo se não existir
if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w") as f:
        json.dump([], f)


def carregar_pedidos():
    with open(ORDERS_FILE, "r") as f:
        return json.load(f)


def salvar_pedidos(pedidos):
    with open(ORDERS_FILE, "w") as f:
        json.dump(pedidos, f, indent=4)


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

    except:
        return None


@app.route("/")
def home():
    return "Servico de Pedidos Online"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# Criar pedido
@app.route("/orders", methods=["POST"])
def criar_pedido():

    usuario = verificar_token()

    if not usuario:
        return jsonify({
            "erro": "Token invalido"
        }), 401

    dados = request.json

    pedidos = carregar_pedidos()

    novo_pedido = {
        "id": len(pedidos) + 1,
        "userId": usuario["userId"],
        "productId": dados["productId"]
    }

    pedidos.append(novo_pedido)

    salvar_pedidos(pedidos)

    return jsonify(novo_pedido), 201


# Listar pedidos de um usuário
@app.route("/orders/<int:user_id>", methods=["GET"])
def listar_pedidos(user_id):

    usuario = verificar_token()

    if not usuario:
        return jsonify({
            "erro": "Token invalido"
        }), 401

    pedidos = carregar_pedidos()

    pedidos_usuario = []

    for pedido in pedidos:

        if pedido["userId"] == user_id:
            pedidos_usuario.append(pedido)

    return jsonify(pedidos_usuario)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5003,
        debug=True
    )