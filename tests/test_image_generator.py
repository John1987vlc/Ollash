import asyncio
from pathlib import Path

from dotenv import load_dotenv  # Import load_dotenv

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.structured_logger import StructuredLogger
from backend.utils.domains.multimedia.image_generation_tools import ImageGeneratorTools


async def main():
    load_dotenv()  # Load environment variables from .env

    log_file = Path("test_image_generator.log")
    structured_logger = StructuredLogger(log_file)
    logger = AgentLogger(structured_logger)

    generator = ImageGeneratorTools(logger=logger)

    print("Generating a test image...")
    result = await generator.generate_image(prompt="a photo of a cat sitting on a table")

    if result["ok"]:
        print(f"Image generated successfully: {result['path']}")
    else:
        print(f"Image generation failed: {result['error']}")

    await generator.close_session()


if __name__ == "__main__":
    asyncio.run(main())
