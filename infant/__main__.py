"""
Entry point for running the infant module as a CLI application.
Usage: python -m infant
"""
import asyncio
from infant.main import main

if __name__ == "__main__":
    asyncio.run(main())
