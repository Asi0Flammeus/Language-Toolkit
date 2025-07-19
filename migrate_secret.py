#!/usr/bin/env python3
"""
Migration script to help users set up JWT secrets, client credentials,
and migrate existing JSON configuration to .env file.

This script guides users through:
1. Creating a secure JWT secret key
2. Setting up client credentials
3. Migrating api_keys.json to .env file
4. Creating appropriate .env and client_credentials.json files
5. Preserving existing configurations during migration
"""

import json
import os
import secrets
import string
from pathlib import Path
import sys


def generate_secure_secret(length: int = 32) -> str:
    """Generate a cryptographically secure random secret."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_client_credentials() -> tuple[str, str]:
    """Generate a secure client_id and client_secret pair."""
    client_id = f"client_{secrets.token_urlsafe(16)}"
    client_secret = secrets.token_urlsafe(32)
    return client_id, client_secret


def migrate_api_keys_to_env(env_content: str) -> str:
    """Migrate api_keys.json to .env format."""
    api_keys_file = Path("api_keys.json")
    
    if not api_keys_file.exists():
        print("ℹ️  No api_keys.json found to migrate")
        return env_content
    
    print("📋 Found api_keys.json, migrating to .env...")
    
    try:
        with open(api_keys_file, 'r') as f:
            api_keys = json.load(f)
        
        # Check if API keys section exists
        if "# API Keys" not in env_content:
            env_content = env_content.rstrip() + "\n\n# API Keys\n"
        
        # Map JSON keys to env variable names
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepl": "DEEPL_API_KEY",
            "convertapi": "CONVERTAPI_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY"
        }
        
        # Add each API key to env content
        for json_key, env_key in key_mapping.items():
            if json_key in api_keys and api_keys[json_key]:
                # Check if key already exists in env
                if f"{env_key}=" not in env_content:
                    env_content += f'{env_key}="{api_keys[json_key]}"\n'
                else:
                    # Update existing key
                    lines = env_content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith(f"{env_key}="):
                            lines[i] = f'{env_key}="{api_keys[json_key]}"'
                            break
                    env_content = '\n'.join(lines)
        
        # Rename api_keys.json to api_keys.json.migrated
        migrated_file = api_keys_file.with_suffix('.json.migrated')
        api_keys_file.rename(migrated_file)
        print(f"✅ Migrated api_keys.json to .env (backed up as {migrated_file})")
        
    except Exception as e:
        print(f"⚠️  Error migrating api_keys.json: {e}")
    
    return env_content


def check_migration_needed() -> bool:
    """Check if migration is needed."""
    env_file = Path(".env")
    api_keys_file = Path("api_keys.json")
    creds_file = Path("client_credentials.json")
    
    # If .env doesn't exist but api_keys.json does, migration is needed
    if not env_file.exists() and api_keys_file.exists():
        return True
    
    # If .env exists but is missing critical values
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            if 'SECRET_KEY=' not in content or 'SECRET_KEY="CHANGE_ME"' in content:
                return True
        except:
            pass
    
    # If client credentials don't exist
    if not creds_file.exists():
        return True
    
    return False


def run_silent_migration():
    """Run migration silently if needed (for automatic execution)."""
    if not check_migration_needed():
        return
    
    print("🔄 Running automatic configuration migration...")
    
    env_file = Path(".env")
    creds_file = Path("client_credentials.json")
    
    # Create or update .env file
    env_content = ""
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
    
    # Ensure JWT secret exists
    if 'SECRET_KEY=' not in env_content or 'SECRET_KEY="CHANGE_ME"' in env_content:
        jwt_secret = generate_secure_secret(64)
        if 'SECRET_KEY=' in env_content:
            lines = env_content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('SECRET_KEY='):
                    lines[i] = f'SECRET_KEY="{jwt_secret}"'
                    break
            env_content = '\n'.join(lines)
        else:
            env_content = f'# JWT Authentication\nSECRET_KEY="{jwt_secret}"\nACCESS_TOKEN_EXPIRE_MINUTES=60\n\n' + env_content
    
    # Migrate API keys
    env_content = migrate_api_keys_to_env(env_content)
    
    # Write .env file
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    # Create client credentials if needed
    if not creds_file.exists():
        client_id, client_secret = generate_client_credentials()
        creds_data = {
            "clients": [{
                "client_id": client_id,
                "client_secret": client_secret,
                "description": "Auto-generated client"
            }]
        }
        with open(creds_file, 'w') as f:
            json.dump(creds_data, f, indent=2)
        
        print(f"✅ Generated client credentials: {client_id}")
    
    print("✅ Configuration migration completed")


def main():
    # Check if running in auto mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_silent_migration()
        return
    
    print("=" * 60)
    print("Language Toolkit API Secret Migration Tool")
    print("=" * 60)
    print()
    
    # Check for existing files
    env_file = Path(".env")
    creds_file = Path("client_credentials.json")
    
    # Handle .env file
    print("Setting up JWT secret key...")
    
    if env_file.exists():
        print(f"⚠️  Found existing .env file")
        response = input("Do you want to update it? (y/N): ").lower()
        if response != 'y':
            print("Keeping existing .env file")
        else:
            # Read existing content
            with open(env_file, 'r') as f:
                existing_content = f.read()
            
            # Generate new secret
            jwt_secret = generate_secure_secret(64)
            
            # Update or add SECRET_KEY
            if "SECRET_KEY=" in existing_content:
                lines = existing_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("SECRET_KEY="):
                        lines[i] = f'SECRET_KEY="{jwt_secret}"'
                        break
                new_content = '\n'.join(lines)
            else:
                new_content = existing_content.rstrip() + f'\n\n# JWT Authentication\nSECRET_KEY="{jwt_secret}"\nACCESS_TOKEN_EXPIRE_MINUTES=60\n'
            
            # Migrate API keys from JSON
            new_content = migrate_api_keys_to_env(new_content)
            
            # Write updated content
            with open(env_file, 'w') as f:
                f.write(new_content)
            
            print("✅ Updated .env file with new JWT secret")
    else:
        # Create new .env file
        jwt_secret = generate_secure_secret(64)
        env_content = f'''# Language Toolkit API Configuration

# JWT Authentication
SECRET_KEY="{jwt_secret}"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# API Keys
# (Will be populated from api_keys.json if it exists)

# AWS Configuration (for S3 operations)
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key
# AWS_DEFAULT_REGION=us-east-1
# S3_BUCKET_NAME=your_bucket_name
'''
        # Migrate API keys if available
        env_content = migrate_api_keys_to_env(env_content)
        
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created .env file with secure JWT secret")
    
    print()
    
    # Handle client credentials
    print("Setting up client credentials...")
    
    if creds_file.exists():
        print(f"⚠️  Found existing client_credentials.json")
        response = input("Do you want to add a new client? (y/N): ").lower()
        if response != 'y':
            print("Keeping existing client credentials")
            return
        
        # Read existing credentials
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)
    else:
        # Start with example file structure
        creds_data = {"clients": []}
    
    # Generate new client credentials
    client_id, client_secret = generate_client_credentials()
    
    print()
    print("Generated new client credentials:")
    print(f"  Client ID:     {client_id}")
    print(f"  Client Secret: {client_secret}")
    print()
    print("⚠️  IMPORTANT: Save these credentials securely!")
    print("    The client secret will not be shown again.")
    print()
    
    # Add to credentials file
    creds_data["clients"].append({
        "client_id": client_id,
        "client_secret": client_secret,
        "description": input("Enter a description for this client (e.g., 'Frontend App'): ") or "API Client"
    })
    
    # Write credentials file
    with open(creds_file, 'w') as f:
        json.dump(creds_data, f, indent=2)
    
    print(f"✅ Saved client credentials to {creds_file}")
    
    # Create example file if it doesn't exist
    example_file = Path("client_credentials.json.example")
    if not example_file.exists():
        with open(example_file, 'w') as f:
            json.dump({
                "clients": [
                    {
                        "client_id": "client_example_id",
                        "client_secret": "client_example_secret",
                        "description": "Example client - DO NOT USE IN PRODUCTION"
                    }
                ]
            }, f, indent=2)
        print(f"✅ Created {example_file} for reference")
    
    print()
    print("=" * 60)
    print("Migration complete!")
    print()
    print("Next steps:")
    print("1. Review and update your .env file with required API keys")
    print("2. Keep your client credentials secure")
    print("3. Use the client_id and client_secret to obtain JWT tokens:")
    print()
    print("   curl -X POST http://localhost:8000/token \\")
    print("     -d 'username=<client_id>&password=<client_secret>'")
    print()
    print("4. Use the returned access_token in API requests:")
    print()
    print("   curl -H 'Authorization: Bearer <access_token>' \\")
    print("     http://localhost:8000/api/endpoint")
    print()
    
    # Add to .gitignore if needed
    gitignore = Path(".gitignore")
    if gitignore.exists():
        with open(gitignore, 'r') as f:
            gitignore_content = f.read()
        
        files_to_ignore = [".env", "client_credentials.json"]
        missing_ignores = [f for f in files_to_ignore if f not in gitignore_content]
        
        if missing_ignores:
            print("⚠️  Adding security files to .gitignore...")
            with open(gitignore, 'a') as f:
                f.write("\n# Security files\n")
                for file in missing_ignores:
                    f.write(f"{file}\n")
            print("✅ Updated .gitignore")


if __name__ == "__main__":
    main()