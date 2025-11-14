"""
Neo4j Setup Script
Prompts user for Neo4j connection details and creates a .env file
"""

import os
import sys
from pathlib import Path
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError


def test_connection(uri: str, user: str, password: str) -> tuple[bool, str]:
    """
    Test Neo4j connection
    
    Returns:
        Tuple of (success, error_message)
    """
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        driver.close()
        return True, ""
    except ServiceUnavailable as e:
        return False, f"Service unavailable: {e}"
    except AuthError as e:
        return False, f"Authentication failed: {e}"
    except Exception as e:
        return False, f"Connection error: {e}"


def create_env_file(uri: str, user: str, password: str, env_path: str) -> bool:
    """
    Create or update .env file with Neo4j credentials
    
    Args:
        uri: Neo4j URI
        user: Neo4j username
        password: Neo4j password
        env_path: Path to .env file
    
    Returns:
        True if successful
    """
    try:
        # Read existing .env if it exists
        existing_env = {}
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_env[key.strip()] = value.strip()
        
        # Update with new Neo4j credentials
        existing_env['NEO4J_URI'] = uri
        existing_env['NEO4J_USER'] = user
        existing_env['NEO4J_PASSWORD'] = password
        
        # Write back to .env
        with open(env_path, 'w') as f:
            f.write("# Neo4j Configuration\n")
            for key, value in existing_env.items():
                f.write(f"{key}={value}\n")
        
        print(f"\n✓ Environment file created/updated: {env_path}")
        return True
    
    except Exception as e:
        print(f"\n✗ Error creating .env file: {e}")
        return False


def load_env_file(env_path: str):
    """Load environment variables from .env file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


def prompt_for_credentials() -> tuple[str, str, str]:
    """
    Prompt user for Neo4j connection details
    
    Returns:
        Tuple of (uri, user, password)
    """
    print("\n" + "="*50)
    print("Neo4j Database Setup")
    print("="*50)
    print("\nPlease provide your Neo4j connection details.")
    print("If you don't have Neo4j installed, visit: https://neo4j.com/download/")
    print()
    
    # Neo4j URI
    print("Neo4j URI (Connection String)")
    print("  Examples:")
    print("    - Local: bolt://localhost:7687")
    print("    - Aura: neo4j+s://xxxxx.databases.neo4j.io")
    print("    - Remote: bolt://your-server:7687")
    uri_default = "bolt://localhost:7687"
    uri = input(f"Enter URI [default: {uri_default}]: ").strip()
    if not uri:
        uri = uri_default
    
    # Neo4j Username
    print("\nNeo4j Username")
    user_default = "neo4j"
    user = input(f"Enter username [default: {user_default}]: ").strip()
    if not user:
        user = user_default
    
    # Neo4j Password
    print("\nNeo4j Password")
    print("  (Note: For new Neo4j installations, the default password is 'neo4j'")
    print("   but you'll be prompted to change it on first login)")
    password = input("Enter password: ").strip()
    
    if not password:
        print("\n✗ Error: Password cannot be empty")
        sys.exit(1)
    
    return uri, user, password


def main():
    """Main setup function"""
    
    # Determine .env file path (in the same directory as this script)
    script_dir = Path(__file__).parent
    env_path = script_dir / ".env"
    
    print("\n" + "="*50)
    print("Neo4j Setup Wizard")
    print("="*50)
    
    # Check if .env already exists
    if env_path.exists():
        print(f"\nFound existing .env file at: {env_path}")
        use_existing = input("Do you want to use existing credentials? (y/n): ").strip().lower()
        
        if use_existing == 'y':
            load_env_file(str(env_path))
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "")
            
            if not password or password.strip() == "":
                print("\n✗ No password found in .env file")
                uri, user, password = prompt_for_credentials()
            else:
                print(f"\nTesting existing connection to {uri}...")
                success, error = test_connection(uri, user, password)
                
                if success:
                    print("✓ Connection successful!")
                    print("\nSetup complete. You can now run embed_documents.py")
                    return
                else:
                    print(f"✗ Connection failed: {error}")
                    print("\nPlease enter new credentials")
                    uri, user, password = prompt_for_credentials()
        else:
            uri, user, password = prompt_for_credentials()
    else:
        uri, user, password = prompt_for_credentials()
    
    # Test the connection
    print(f"\nTesting connection to {uri}...")
    success, error = test_connection(uri, user, password)
    
    if not success:
        print(f"\n✗ Connection failed: {error}")
        print("\nPlease check your credentials and ensure Neo4j is running.")
        print("\nCommon issues:")
        print("  1. Neo4j service is not running")
        print("  2. Incorrect URI (check host and port)")
        print("  3. Invalid username or password")
        print("  4. Firewall blocking the connection")
        
        retry = input("\nWould you like to try different credentials? (y/n): ").strip().lower()
        if retry == 'y':
            main()  # Recursive retry
        else:
            sys.exit(1)
    
    print("✓ Connection successful!")
    
    # Create .env file
    if create_env_file(uri, user, password, str(env_path)):
        print("\n" + "="*50)
        print("Setup Complete!")
        print("="*50)
        print(f"\nConnection details saved to: {env_path}")
        print("\nYou can now run embed_documents.py to process your documents.")
        print("\nNote: The .env file contains sensitive credentials.")
        print("      Make sure to add it to your .gitignore file!")
        
        # Check for .gitignore
        gitignore_path = script_dir / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()
            if '.env' not in gitignore_content:
                print("\n⚠ Warning: .env is not in your .gitignore file")
                add_to_gitignore = input("Add .env to .gitignore? (y/n): ").strip().lower()
                if add_to_gitignore == 'y':
                    with open(gitignore_path, 'a') as f:
                        f.write("\n# Environment variables\n.env\n")
                    print("✓ Added .env to .gitignore")
        else:
            create_gitignore = input("\nCreate .gitignore file to protect credentials? (y/n): ").strip().lower()
            if create_gitignore == 'y':
                with open(gitignore_path, 'w') as f:
                    f.write("# Environment variables\n.env\n")
                print("✓ Created .gitignore and added .env")
    else:
        print("\n✗ Failed to create .env file")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
