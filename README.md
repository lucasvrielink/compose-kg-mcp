# compose-kg-mcp

Para subir o neo4j, crie um arquivo .env contendo NEO4J_PASSWORD=SUA_KEY

docker compose up -d

crie uma venv
pip install -r requirements.txt

Execute o parser.

Abra o site http://localhost:7474/ e se logue com o usuário 'neo4j' e a senha do env.

Execute

MATCH(n) RETURN n
