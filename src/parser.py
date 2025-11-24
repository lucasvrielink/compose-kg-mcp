import yaml
import re
import os
import glob
from neo4j import GraphDatabase, basic_auth
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = os.environ.get('NEO4J_PASSWORD')

COMPOSE_DIR = 'docker_composes'
COMPOSE_PATTERN = 'docker-compose-*.yml'
URI_BASE = "http://infra.knowledge/docker#"


def execute_cypher_commands(commands: List[str], context_name: str, step_description: str):

    try:
        driver = GraphDatabase.driver(URI, auth=basic_auth(USER, PASSWORD))
        driver.verify_connectivity()
        
        with driver.session() as session:
            for i, command in enumerate(commands):
                try:
                    session.run(command)
                except Exception as e:
                    print(f"\n Erro no comando {i+1} ({step_description}): {command}")
                    raise e
            
            print(f"    [{step_description}] {len(commands)} comandos aplicados em '{context_name}'.")

    except Exception as e:
        print(f"\n Falha Neo4j: {e}")
    finally:
        if 'driver' in locals() and driver:
            driver.close()


def sanitize(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text))


def generate_service_base_nodes(yaml_data: Dict, file_name: str) -> List[str]:
    commands = []
    file_prefix = sanitize(file_name.replace('.yml', '')) + "_"
    services = yaml_data.get('services', {})
    
    for service_name in services.keys():
        safe_service_name = sanitize(service_name)
        unique_variable_name = f"{file_prefix}{safe_service_name}"
        service_uri = f"{URI_BASE}{unique_variable_name}"
        
        commands.append(
            f"MERGE (s:Service {{uri: '{service_uri}'}}) "
            f"SET s.serviceName = '{service_name}', "
            f"    s.composeFile = '{file_name}', "
            f"    s.name = '{service_name}'"
        )
    return commands


def generate_service_detail_commands(yaml_data: Dict, file_name: str, service_name: str, config: Dict) -> List[str]:

    commands = []
    
    file_prefix = sanitize(file_name.replace('.yml', '')) + "_"
    safe_service_name = sanitize(service_name)
    unique_variable_name = f"{file_prefix}{safe_service_name}"
    
    service_uri = f"{URI_BASE}{unique_variable_name}"
    
    # Busca o serviço e remove relações antigas
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:EXPOSES_PORT]->() DELETE r")
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:MOUNTS_VOLUME]->() DELETE r")
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:HAS_ENV_VAR]->() DELETE r")
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:USES_IMAGE]->() DELETE r")
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:CONNECTS_TO]->() DELETE r")
    commands.append(f"MATCH (s:Service {{uri: '{service_uri}'}})-[r:DEPENDS_ON]->() DELETE r")

    # Imagem
    if 'image' in config:
        image_full = config['image']
        image_name, image_version = image_full.split(':', 1) if ':' in image_full else (image_full, 'latest')
        safe_img_id = f"{sanitize(image_name)}_{sanitize(image_version)}"
        image_uri = f"{URI_BASE}image/{safe_img_id}"
        
        commands.append(
            f"MERGE (i:Image {{uri: '{image_uri}'}}) "
            f"SET i.imageName = '{image_name}', i.imageVersion = '{image_version}', i.name = '{image_name}'"
        )

        commands.append(
            f"MATCH (s:Service {{uri: '{service_uri}'}}), (i:Image {{uri: '{image_uri}'}}) "
            f"MERGE (s)-[:USES_IMAGE]->(i)"
        )

    # Portas
    ports_list = config.get('ports') or []
    for port_mapping in ports_list:
        parts = str(port_mapping).split(':')
        protocol = 'tcp'
        if '/' in parts[-1]:
            parts[-1], protocol = parts[-1].split('/', 1)
        host_port = parts[0] if len(parts) == 2 else parts[-1]
        container_port = parts[-1]
        
        port_uri = f"{URI_BASE}port/{host_port}/{protocol}"
        port_display = f"{host_port}:{container_port}/{protocol}"
        
        commands.append(
            f"MERGE (p:PortMapping {{uri: '{port_uri}'}}) "
            f"SET p.hostPort = toInteger({host_port}), p.containerPort = toInteger({container_port}), "
            f"    p.protocol = '{protocol}', p.name = '{port_display}'"
        )
        commands.append(
            f"MATCH (s:Service {{uri: '{service_uri}'}}), (p:PortMapping {{uri: '{port_uri}'}}) "
            f"MERGE (s)-[:EXPOSES_PORT]->(p)"
        )

    # Variáveis de ambiente
    environment = config.get('environment')
    env_vars = {}
    if isinstance(environment, list):
        for item in environment:
            if '=' in item:
                k, v = item.split('=', 1)
                env_vars[k] = v
    elif isinstance(environment, dict):
        env_vars = environment
        
    for key, value in env_vars.items():
        safe_key = sanitize(key)

        unique_env_id = f"{unique_variable_name}_{safe_key}"
        env_uri = f"{URI_BASE}{unique_env_id}"
        safe_val = str(value).replace("'", "\\'")
        
        commands.append(
            f"MERGE (ev:EnvironmentVariable {{uri: '{env_uri}'}}) "
            f"SET ev.varKey = '{key}', ev.varValue = '{safe_val}', ev.name = '{key}'"
        )

        commands.append(
            f"MATCH (s:Service {{uri: '{service_uri}'}}), (ev:EnvironmentVariable {{uri: '{env_uri}'}}) "
            f"MERGE (s)-[:HAS_ENV_VAR]->(ev)"
        )

    # Volumes
    volumes_list = config.get('volumes') or []
    for volume_mapping in volumes_list:
        parts = str(volume_mapping).split(':', 1)
        host_path, container_path = (parts[0], parts[0]) if len(parts) == 1 else parts
        
        vol_id = f"{unique_variable_name}_{sanitize(container_path)}"
        vol_uri = f"{URI_BASE}volume/{vol_id}"
        
        commands.append(
            f"MERGE (v:Volume {{uri: '{vol_uri}'}}) "
            f"SET v.hostPath = '{host_path.replace("'", "\\'")}', v.containerPath = '{container_path.replace("'", "\\'")}', v.name = '{container_path}'"
        )
        commands.append(
            f"MATCH (s:Service {{uri: '{service_uri}'}}), (v:Volume {{uri: '{vol_uri}'}}) "
            f"MERGE (s)-[:MOUNTS_VOLUME]->(v)"
        )

    # Dependencia
    dependencies = config.get('depends_on') or []
    for dependency in dependencies:
        target_unique_name = f"{file_prefix}{sanitize(dependency)}"
        target_uri = f"{URI_BASE}{target_unique_name}"
        
        commands.append(
            f"MATCH (s1:Service {{uri: '{service_uri}'}}), "
            f"      (s2:Service {{uri: '{target_uri}'}}) "
            f"MERGE (s1)-[:DEPENDS_ON]->(s2)"
        )

    # Networks
    networks_list = config.get('networks') or []
    network_names = []
    if isinstance(networks_list, list): network_names = networks_list
    elif isinstance(networks_list, dict): network_names = list(networks_list.keys())
        
    for net_entry in network_names:
        net_name = net_entry['name'] if isinstance(net_entry, dict) and 'name' in net_entry else str(net_entry)
        net_uri = f"{URI_BASE}network/{sanitize(net_name)}"
        
        commands.append(
            f"MERGE (n:Network {{uri: '{net_uri}'}}) SET n.name = '{net_name}'"
        )
        commands.append(
            f"MATCH (s:Service {{uri: '{service_uri}'}}), (n:Network {{uri: '{net_uri}'}}) "
            f"MERGE (s)-[:CONNECTS_TO]->(n)"
        )

    return commands


if __name__ == '__main__':
    search_path = os.path.join('./src/docker_composes/', '*.yaml')
    compose_files = glob.glob(search_path)
    
    print(f"\n Parsing iniciado.")
    
    if not compose_files:
        print("Nenhum arquivo encontrado.")
        exit(1)

    for file_path in compose_files:
        file_name = os.path.basename(file_path)
        print(f"\n Processando: {file_name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            base_commands = generate_service_base_nodes(yaml_data, file_name)
            execute_cypher_commands(base_commands, file_name, "Base Structure")
            
            services = yaml_data.get('services', {})
            for service_name, config in services.items():
                detail_commands = generate_service_detail_commands(yaml_data, file_name, service_name, config)
                execute_cypher_commands(detail_commands, service_name, "Details & Relations")

        except Exception as e:
            print(f"Erro: {e}")

    print("\n Processamento concluído!")