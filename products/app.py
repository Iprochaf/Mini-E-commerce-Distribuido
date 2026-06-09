from flask import Flask, request, jsonify
import json
import os
import jwt

app = Flask(__name__)

SECRET_KEY = "senha123"

PRIMARY_FILE = "products_primary.json"
REPLICA_FILE = "products_replica.json"

# Cria os arquivos caso não existam
for arquivo in [PRIMARY_FILE, REPLICA_FILE]:
    if not os.path.exists(arquivo):
        with open(arquivo, "w") as f:
            json.dump([], f)

# Controle de round-robin
round_robin = 0


def carregar_produtos(arquivo):
    with open(arquivo, "r") as f:
        return json.load(f)


def salvar_produtos(arquivo, produtos):
    with open(arquivo, "w") as f:
        json.dump(produtos, f, indent=4)


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
    return "Servico de Produtos Online"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/products", methods=["GET"])
def listar_produtos():

    global round_robin

    if round_robin == 0:
        produtos = carregar_produtos(PRIMARY_FILE)
        round_robin = 1
    else:
        produtos = carregar_produtos(REPLICA_FILE)
        round_robin = 0

    return jsonify(produtos)


@app.route("/products/<int:product_id>", methods=["GET"])
def buscar_produto(product_id):

    produtos = carregar_produtos(PRIMARY_FILE)

    for produto in produtos:

        if produto["id"] == product_id:
            return jsonify(produto)

    return jsonify({
        "erro": "Produto nao encontrado"
    }), 404


@app.route("/products", methods=["POST"])
def criar_produto():

    usuario = verificar_token()

    if not usuario:
        return jsonify({
            "erro": "Token invalido"
        }), 401

    if usuario["role"] != "admin":
        return jsonify({
            "erro": "Apenas administradores podem criar produtos"
        }), 403

    dados = request.json

    if not dados:
        return jsonify({
            "erro": "JSON invalido"
        }), 400

    produtos = carregar_produtos(PRIMARY_FILE)

    novo_produto = {
        "id": len(produtos) + 1,
        "nome": dados["nome"],
        "preco": dados["preco"]
    }

    produtos.append(novo_produto)

    # Replicacao obrigatoria
    salvar_produtos(PRIMARY_FILE, produtos)
    salvar_produtos(REPLICA_FILE, produtos)

    return jsonify(novo_produto), 201


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )