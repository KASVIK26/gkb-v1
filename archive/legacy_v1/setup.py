"""Setup script to initialize Neo4j with constraints and seed data."""

from __future__ import annotations

import sys

from curator.db import DBConfig, DBDriver
from curator.init_constraints import create_constraints
from curator.seed_loader import load_seed_data


def main() -> int:
    """Initialize Neo4j instance with constraints and seed data."""
    print("🌾 AgriHub KB — Database Setup")
    print("=" * 50)
    
    try:
        # Load config and connect
        print("\n1️⃣  Connecting to Neo4j...")
        config = DBConfig()
        config.validate()
        
        driver = DBDriver(config)
        driver.connect()
        
        # Create constraints
        print("\n2️⃣  Creating uniqueness constraints...")
        create_constraints(driver)
        
        # Load seed data
        print("\n3️⃣  Loading 22 seed gene-disease edges...")
        edge_count = load_seed_data(driver)
        
        print("\n" + "=" * 50)
        print(f"✓ Setup complete: {edge_count} edges loaded")
        print("  Next: run the GFF parser and API layer")
        
        driver.close()
        return 0
    
    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
        print("   Make sure .env has NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        return 1
    
    except ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        print("   Check your Neo4j URI and credentials")
        return 1
    
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
