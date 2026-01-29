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
    Returns full technical configuration: Image, Ports, Envs, Volumes.
    Useful for security auditing (checking :latest tags or exposed secrets).
    """
    query = """
    MATCH (s:Service {serviceName: $name})
        OPTIONAL MATCH (s)-[:USES_IMAGE]->(i:Image)
        OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:PortMapping)
        OPTIONAL MATCH (s)-[:HAS_ENV_VAR]->(ev:EnvironmentVariable)
        OPTIONAL MATCH (s)-[:MOUNTS_VOLUME]->(v:Volume)
    RETURN 
        s.serviceName as service,
        i.imageName + ':' + i.imageVersion as image_full,
        collect(DISTINCT p.name) as ports,
        collect(DISTINCT ev.varKey + '=' + ev.varValue) as environment,
        collect(DISTINCT v.hostPath + ':' + v.containerPath) as volumes
    """
    return run_cypher(query, {"name": service_name})

@mcp.tool()
def check_port_conflicts():
    """
    Scans for host port collisions across all services.
    """
    query = """
    MATCH (s:Service)-[:EXPOSES_PORT]->(p:PortMapping)
    WITH p.hostPort as host_port, collect(s.name) as conflicting_services, count(s) as count
    WHERE count > 1
    RETURN 
        host_port,
        conflicting_services as involved_services,
        "CRITICAL: Port conflict detected" as status
    """
    return run_cypher(query)

@mcp.tool()
def find_impact_analysis(service_name: str):
    """
    Returns ALL services that directly or indirectly depend on the target service
    using transitive dependency traversal (DEPENDS_ON*).
    """
    query = """
    MATCH (target:Service {name: $name})
    MATCH (downstream:Service)-[:DEPENDS_ON*]->(target)
    RETURN 
        target.name as failed_service,
        collect(DISTINCT downstream.name) as affected_services_chain,
        count(downstream) as total_impacted
    """
    return run_cypher(query, {"name": service_name})

@mcp.tool()
def check_volume_conflicts():
    """
    Identifies if multiple services are mounting the same Host Path,
    which can lead to data corruption (Race Conditions).
    """
    query = """
    MATCH (s:Service)-[:MOUNTS_VOLUME]->(v:Volume)
    WITH v.hostPath as host_path, collect(s.name) as services, count(s) as count
    WHERE count > 1
    RETURN 
        host_path,
        services as conflicting_services,
        "CRITICAL: Multiple writers on same host path" as status
    """
    return run_cypher(query)

@mcp.tool()
def analyze_network_reachability(source_service: str, target_service: str):
    """
    Uses Graph ShortestPath algorithm to find if a physical network path exists
    between two services, specifically looking for 'bridge' containers that bypass isolation.
    """
    query = """
    MATCH (source:Service {name: $source}), (target:Service {name: $target})
    MATCH path = shortestPath((source)-[:CONNECTS_TO*]-(target))
    RETURN 
        [n in nodes(path) | coalesce(n.name, n.serviceName)] as attack_path,
        length(path)/2 as network_hops,
        "WARNING: Segmentation Violation Detected" as status
    """
    result = run_cypher(query, {"source": source_service, "target": target_service})
    if not result:
        return f"No path found between '{source_service}' and '{target_service}'. Isolation Confirmed."
    return result

if __name__ == "__main__":
    mcp.run()