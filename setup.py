#!/usr/bin/env python3
"""
Development setup script for Knowledge Base MCP
"""
import subprocess
import sys
import os

def install_requirements():
    """Install Python requirements"""
    print("📦 Installing Python dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def create_env_example():
    """Create example environment file"""
    env_content = """# Knowledge Base MCP Environment Variables

# Required: PostgreSQL/Supabase connection
DATABASE_URL=postgresql://user:password@host:5432/database

# Required: OpenAI API key for embeddings
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Default sources to process
SOURCES=https://arxiv.org/pdf/2408.09869,https://example.com/document.pdf

# Optional: Custom table name
# TABLE_NAME=my_documents
"""

    with open(".env.example", "w") as f:
        f.write(env_content)
    print("📝 Created .env.example file")

def setup_gitignore():
    """Ensure .gitignore exists"""
    if not os.path.exists(".gitignore"):
        print("⚠️  No .gitignore found - create one to protect sensitive files")
    else:
        print("✅ .gitignore exists")

def main():
    print("🚀 Setting up Knowledge Base MCP development environment...")

    try:
        install_requirements()
        create_env_example()
        setup_gitignore()

        print("\n✅ Setup complete!")
        print("\n📋 Next steps:")
        print("1. Copy .env.example to .env and fill in your values")
        print("2. Run: python server.py")
        print("3. Test: python test_load_documents.py")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
