# Mini E-commerce Distribuído — Guia de Execução

Sistema de e-commerce composto por **API Gateway** + **3 microsserviços**
(Usuários, Produtos e Pedidos), com autenticação JWT, replicação síncrona
do serviço de Produtos (primário + réplica) e heartbeat com detecção de
falhas/recuperação.

---

## 1. Requisitos

- [Docker](https://www.docker.com/) e [Docker Compose](https://docs.docker.com/compose/) (v2+)
- Portas livres no host: `5000`, `5001`, `5002`, `5003`, `5004`
- (Opcional, para execução sem Docker) Python 3.12+

---

## 2. Arquitetura

```
                         ┌───────────────────────┐
                         │      API Gateway        │
                         │   (porta 5000)          │
                         │  - Heartbeat (5s)        │
                         │  - Round-robin Products  │
                         └─────┬──────┬──────┬──────┘
                               │      │      │
              ┌────────────────┘      │      └────────────────┐
              ▼                       ▼                        ▼
   ┌─────────────────┐     ┌──────────────────┐      ┌──────────────────┐
   │  users (5001)    │     │  orders (5003)    │      │ products-*        │
   │  - register      │     │  - cria pedido    │      │ primary (5002)    │
   │  - login (JWT)   │     │  - valida produto │◄────►│ replica  (5004)   │
   │  - GET /users/:id│     │    via HTTP       │      │ replicação sync   │
   └─────────────────┘     └──────────────────┘      └──────────────────┘
```

- **Gateway**: ponto único de entrada. Faz *health check* (`/health`) em
  todos os serviços a cada `HEARTBEAT_INTERVAL` segundos. Após **2 falhas
  consecutivas**, marca o serviço como indisponível e passa a responder
  `503` ao cliente. Ao voltar a responder, registra a recuperação em log.
- **Products**: roda em **duas instâncias** (`products-primary` e
  `products-replica`). Toda escrita (`POST /products`) só é confirmada
  ao cliente após o **primário replicar com sucesso para a réplica**
  (consistência forte). Leituras (`GET /products` e `GET /products/:id`)
  são distribuídas em **round-robin real** pelo Gateway entre as duas
  instâncias, com *failover* automático se uma estiver fora do ar.

---

## 3. Executando com Docker Compose (recomendado)

Na raiz do projeto:

```bash
docker compose up --build
```

Isso cria 5 containers:

| Serviço             | Porta no host | Papel                              |
|---------------------|---------------|------------------------------------|
| `gateway`           | 5000          | API Gateway (único ponto de entrada)|
| `users`             | 5001          | Serviço de Usuários                 |
| `products-primary`  | 5002          | Produtos — instância primária       |
| `orders`            | 5003          | Serviço de Pedidos                  |
| `products-replica`  | 5004          | Produtos — instância réplica        |

Para derrubar tudo:

```bash
docker compose down
```

### Variáveis de ambiente

Por padrão, a chave secreta do JWT é `timbu1901` (apenas para fins
acadêmicos). Para customizar, defina `JWT_SECRET_KEY` antes de subir:

```bash
JWT_SECRET_KEY="minha-chave-super-secreta" docker compose up --build
```

---

## 4. Executando sem Docker (modo manual)

Em 4 terminais separados (na pasta de cada serviço), instale as
dependências e exporte as variáveis de ambiente necessárias:

```bash
# Terminal 1 - users
cd users
pip install flask pyjwt bcrypt
python app.py            # porta 5001

# Terminal 2 - products (primary)
cd products
pip install flask pyjwt requests
set ROLE=primary
set DATA_FILE=products_primary.json
set PEER_URL=http://localhost:5004
python app.py            # porta 5002 (PORT padrao)

# Terminal 3 - products (replica)
cd products
set ROLE=replica
set DATA_FILE=products_replica.json
set PORT=5004
python app.py            # porta 5004

# Terminal 4 - orders
cd orders
pip install flask pyjwt requests
set PRODUCTS_URL=http://localhost:5002
python app.py            # porta 5003

# Terminal 5 - gateway
cd gateway
pip install flask requests
set PRODUCTS_PRIMARY_URL=http://localhost:5002
set PRODUCTS_REPLICA_URL=http://localhost:5004
set USERS_URL=http://localhost:5001
set ORDERS_URL=http://localhost:5003
python app.py            # porta 5000
```

> No PowerShell use `$env:VAR="valor"` em vez de `set VAR=valor`.

---

## 5. Usuários pré-cadastrados (seed)

| Email                  | Senha      | Role  |
|------------------------|-----------|-------|
| `admin@ecommerce.com`  | `admin123`| admin |
| `ivan@gmail.com`       | `123456`  | user  |
| `joao@gmail.com`       | `123456`  | user  |
| `maria@gmail.com`      | `123456`  | user  |

### Estratégia de administração

Por segurança, **o campo `role` nunca é aceito no `POST /users/register`**
— todo novo cadastro nasce com `role = "user"`. A criação de
administradores é feita apenas por **provisionamento manual** do arquivo
`users/users.json` (ambiente de confiança/operador do sistema), como o
usuário `admin@ecommerce.com` já incluído no seed. Em um cenário de
produção, isso seria substituído por um endpoint administrativo protegido
ou por um processo de promoção de papel auditado.

---

## 6. Testando o sistema

Veja a seção de **testes manuais (curl)** no final deste documento, ou
importe a coleção em `postman/` no Postman/Insomnia.

### Fluxo básico

1. `POST /users/register` — cria um usuário (`role` sempre `"user"`).
2. `POST /users/login` — retorna um JWT contendo `userId`, `email`,
   `role` e `exp`.
3. `GET /users/:id` — requer o JWT; só o próprio usuário (ou admin)
   pode visualizar o perfil.
4. `GET /products` / `GET /products/:id` — públicos, leitura distribuída
   entre `products-primary` e `products-replica`.
5. `POST /products` — requer JWT de um usuário com `role = "admin"`.
6. `POST /orders` — requer JWT; valida se o `productId` existe (consulta
   HTTP ao serviço de produtos) antes de criar o pedido.
7. `GET /orders/:userId` — requer JWT; usuário só vê os próprios
   pedidos, exceto admin (que vê de qualquer usuário).

### Testando o heartbeat

```bash
# Derrubar a réplica de produtos
docker compose stop products-replica

# Aguardar 2 ciclos de heartbeat (10s) e checar o status no gateway
curl http://localhost:5000/

# Ver o log de falha
docker compose logs gateway | grep FALHA

# Religar e ver o log de recuperação
docker compose start products-replica
sleep 12
docker compose logs gateway | grep RECUPERADO
```

---

## 7. Logs

Cada serviço grava logs em arquivo (dentro do container) e no stdout:

- `gateway.log` — heartbeat, falhas e recuperações de serviços
- `users.log` — registros, logins e tentativas inválidas
- `products.log` — criação de produtos e eventos de replicação
- `orders.log` — criação de pedidos

Para visualizar via Docker Compose:

```bash
docker compose logs -f gateway
```

---

## 8. Limitações conhecidas

Ver `relatorio.md` para a discussão completa de arquitetura, consistência
e limitações.
