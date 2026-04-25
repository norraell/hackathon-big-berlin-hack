"""Initialize database tables."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, close_db


async def main():
    """Initialize database tables."""
    print("🔧 Initializing database...")
    
    try:
        await init_db()
        print("✅ Database initialized successfully!")
        print("\nNext steps:")
        print("  1. Run: python scripts/generate_mock_data.py")
        print("  2. Start the application: python -m app.main")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())