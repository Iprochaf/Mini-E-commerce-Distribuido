from flask import Flask, request, jsonify
import json
import hashlib
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)

senha = "timbu1901"
arquivo = "users.json"

def hash(senha):
    return hashlib.sha256(
        senha.encode()
    ).hexdigest()

@app.route("/")
def home():
    return {
        "msg": "API de usuários funcionando"
    }

@app.route("/users/register", methods = ["GET"])
def register():

    data = request.json
    with open(arquivo, "r") as cadastro:
        users = json.load(cadastro)
    
    user = {
        "id": data["id"],
        "nome": data["nome"],
        "email": data["email"],
        "senha": hash(data["senha"])
    }
    users.append(user)

    with open(arquivo, "w") as cadastro:
        json.dump(users, cadastro)
    
    return jsonify({"msg": "Usuário Cadastrado"})

@app.route("/users/login", methods=["POST"])
def login():

    data = request.json

    with open(arquivo, "r") as conectar:
        users = json.load(conectar)

    for i in users:

        if (
            i["email"] == data["email"]
            and
            i["senha"] == hash(data["senha"])
        ):

            token = jwt.encode(
                {
                    "id": i["id"],
                    "email": i["email"],
                    "nome": i["nome"],
                    "exp": datetime.utcnow() + timedelta(hours=1)
                },
                senha,
                algorithm="HS256"
            )

            return jsonify({"token": token})

    return jsonify({"erro": "Login inválido"}), 401

@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):

    with open("users.json", "r") as f:
        usuarios = json.load(f)

    for usuario in usuarios:
        if usuario["id"] == user_id:
            return jsonify(usuario)

    return jsonify({"erro": "Usuário não encontrado"}), 404


@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(port=5001, debug=True)
    