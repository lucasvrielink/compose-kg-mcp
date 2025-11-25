import os
from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

mcp = FastMCP("Docker Infra Manager")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run_cypher(query: str, params: dict = None):
    try:
        with driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    except Exception as e:
        return f"Erro na query Neo4j: {str(e)}"


@mcp.tool()
def list_all_services():
    query = """
        MATCH (s:Service)
        RETURN s.name as service, s.composeFile as source_file
        ORDER BY s.composeFile, s.name
    """
    return run_cypher(query)

@mcp.tool()
def get_service_details(service_name: str):
    query = """
        MATCH (s:Service {name: $name})
        OPTIONAL MATCH (s)-[:USES_IMAGE]->(i:Image)
        OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:PortMapping)
        OPTIONAL MATCH (s)-[:HAS_ENV_VAR]->(e:EnvironmentVariable)
        RETURN 
            s.name as service,
            i.name as image,
            collect(DISTINCT p.name) as ports,
            collect(DISTINCT e.name + '=' + e.varValue) as env_vars
    """
    return run_cypher(query, {"name": service_name})

@mcp.tool()
def find_dependencies(service_name: str):
    query = """
        MATCH (s:Service {name: $name})<-[:DEPENDS_ON]-(dependent:Service)
        RETURN dependent.name as impacted_service, dependent.composeFile as file
    """
    return run_cypher(query, {"name": service_name})

@mcp.tool()
def check_port_conflicts(port: int):
    query = """
        MATCH (s:Service)-[:EXPOSES_PORT]->(p:PortMapping)
        WHERE p.hostPort = $port
        RETURN s.name as service, p.protocol as protocol, p.containerPort as internal_port
    """
    return run_cypher(query, {"port": port})

@mcp.tool()
def inspect_network_members(network_name: str):
    query = """
        MATCH (n:Network {name: $net_name})<-[:CONNECTS_TO]-(s:Service)
        RETURN s.name as member_service
    """
    return run_cypher(query, {"net_name": network_name})

if __name__ == "__main__":
    mcp.run()