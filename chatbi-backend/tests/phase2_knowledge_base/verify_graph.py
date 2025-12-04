import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from neo4j import GraphDatabase
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_graph")
settings = get_settings()

def verify_graph():
    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    pwd = settings.NEO4J_PASSWORD
    
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    
    try:
        with driver.session() as session:
            # 1. Count Nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            logger.info(f"Total Nodes: {node_count}")
            
            # 2. Count Relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            logger.info(f"Total Relationships: {rel_count}")
            
            # 3. Check specific relationships (e.g., orders -> users)
            result = session.run("""
                MATCH (t1:Table {name: 'orders'})-[r:JOIN_ON]->(t2:Table {name: 'users'})
                RETURN r
            """)
            record = result.single()
            if record:
                rel = record["r"]
                logger.info(f"Verified Relationship: orders({rel.get('left_key')}) -> users({rel.get('right_key')})")
            else:
                logger.warning("Relationship orders -> users NOT FOUND!")

            # 4. Check isolated sub-graphs (Is everything connected?)
            # Just a simple check for nodes with no relationships
            result = session.run("""
                MATCH (t:Table)
                WHERE NOT (t)--()
                RETURN t.name
            """)
            isolated = [record["t.name"] for record in result]
            if isolated:
                logger.info(f"Isolated Tables (No connections): {isolated}")
            else:
                logger.info("All tables have at least one connection.")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    verify_graph()
