# Graph-Based Representation of Infraestructure-as-Code: Enabling Semantic Reasoning for Containerized Systems.

This project was developed as part of the Master's program at PPGC — Programa de Pós-Graduação em Computação, Universidade Federal do Rio Grande do Sul (UFRGS).

_____

This project implements a system that parses Infrastructure-as-Code (specifically docker-compose.yml files) into a Knowledge Graph (Neo4j) using a custom OWL ontology. It then exposes this graph to Large Language Models (LLMs) via the Model Context Protocol (MCP), enabling AI agents to reason about topology, detect port conflicts, and analyze service dependencies with high factual accuracy.

## 🚀 Features
- **Semantic Parsing**: Converts static YAML files into a dynamic Graph Database, mapping Services, Networks, Volumes, Ports, and Environment Variables.

- **Two-Pass Ingestion**: Robust Python parser that handles forward references and ensures idempotency (prevents duplicate nodes).

- **Scope Isolation**: Unique URI generation strategy to prevent property collisions between similar services in different environments (e.g., Production vs. Test).

- **Conflict Detection**: Automatically identifies critical issues like Host Port Collisions across different compose files.

- **MCP Integration**: Exposes semantic tools (find_dependencies, inspect_network, check_port_conflicts) to LLMs like Claude, enabling natural language auditing.

## 📂 Project Structure
```text
compose-kg-mcp/ \
├── mcp_server/ \
│   └── server.py          # The MCP Server implementation \
├── parser_neo4j/           \
│   └── docker_composes/   # Folder with docker compose files for parsing onto neo4j \
│   └── parser.py          # The ETL script (YAML -> Neo4j) \
├── ontology/           \
│   └── base_ontology.ttl  # The OWL Ontology definition \
├── docker_compose.yaml    # Neo4j docker compose \
├── requirements.txt       # Python dependencies \
├── .env                   # Environment variables (GitIgnored) \
└── README.md \
```

## 📚 Ontology

The Knowledge Graph schema is based on the Docker Infrastructure Ontology, defined in docker_infra.ttl. Key classes include:

- ```:Service```

- ```:Image```

- ```:PortMapping (with properties hostPort, protocol)```

- ```:EnvironmentVariable (Scoped by Service URI)```

- ```:Network```

- ```:Volume```

## 🧠 Example Prompts
Once connected, you can ask Claude questions like:

- "Analyze the dependency chain for the kibana service."

- "Check if there are any critical port conflicts on the host."

- "List all services connected to the elastic network."


