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
    """
    Returns the full technical configuration of a specific service.
    Use this to inspect:
    - Docker Image and Tag
    - Open Ports (Host:Container)
    - Environment Variables (Key=Value)
    - Mounted Volumes (HostPath:ContainerPath)
    """
    query = """
    MATCH (s:Service {serviceName: $name})
        OPTIONAL MATCH (s)-[:USES_IMAGE]->(i:Image)
        OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:PortMapping)
        OPTIONAL MATCH (s)-[:HAS_ENV_VAR]->(ev:EnvironmentVariable)
        OPTIONAL MATCH (s)-[:MOUNTS_VOLUME]->(v:Volume)
    RETURN 
        s.serviceName as service,
        i.name as image,
        collect(DISTINCT p.name) as ports,
        collect(DISTINCT ev.varKey + '=' + ev.varValue) as environment,
        collect(DISTINCT v.hostPath + ':' + v.containerPath) as volumes
    """
    return run_cypher(query, {"name": service_name})

@mcp.tool()
def check_port_conflicts():
    """
    Scans the entire host infrastructure for port collisions.
    Returns a list of host ports that are claimed by more than one service.
    """
    query = """
    MATCH (s:Service)-[:EXPOSES_PORT]->(p:PortMapping)
    WITH p.hostPort as host_port, collect(s.name) as conflicting_services, count(s) as count
    WHERE count > 1
    RETURN 
        host_port,
        conflicting_services as involved_services,
        "Port conflict detected" as status
    """
    return run_cypher(query)

@mcp.tool()
def find_service_dependencies(service_name: str):
    """
    Analyzes the dependency chain for a specific service.
    Returns both direct dependencies (what it needs) and reverse dependencies (what needs it).
    """
    query = """
    MATCH (s:Service {name: $name})
    
    OPTIONAL MATCH (s)-[:DEPENDS_ON]->(upstream:Service)
    OPTIONAL MATCH (downstream:Service)-[:DEPENDS_ON]->(s)
    
    RETURN 
        s.name as analyzed_service,
        collect(DISTINCT upstream.name) as depends_on,
        collect(DISTINCT downstream.name) as required_by
    """
    return run_cypher(query, {"name": service_name})


@mcp.tool()
def inspect_network_members(network_name: str):
    """
    Returns all services connected to a specific Docker network.
    Useful for validating isolation policies.
    """
    query = """
        MATCH (n:Network {name: $net_name})<-[:CONNECTS_TO]-(s:Service)
        RETURN s.name as member_service
    """
    return run_cypher(query, {"net_name": network_name})

if __name__ == "__main__":
    mcp.run()