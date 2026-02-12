"""
Example: Using Image Generator Tool with Auto Agent

This example demonstrates how to use the new Image Generator Tools
to create projects that include automatically generated images.

The auto_agent can now pass prompts to generate images when needed
during project creation.
"""

import os
import sys
from pathlib import Path

# Example 1: Creating a web app with AI-generated assets
# ==================================================

example_1_description = """
Create a professional modern dashboard web application with:

1. Frontend (React + TypeScript):
   - Header with navigation
   - Sidebar menu
   - Main dashboard with 4 statistical cards
   - Chart component showing sales data
   - Responsive design (works on mobile)

2. Assets that need to be generated:
   - Dashboard background image (1920x1080): "Modern tech dashboard background, dark blue gradient with geometric patterns, professional, 4K quality"
   - Company logo (256x256): "Modern tech company logo, minimalist style, blue and white colors, professional, square format"
   - Icon set: 4 different icons (128x128 each) for stats (users, revenue, growth, orders)
   - Hero section background: "Professional office workspace with laptop, modern lighting, minimalist style"

3. Styling:
   - Dark theme with blue accents
   - Smooth animations and transitions
   - Professional typography

4. Data:
   - Sample JSON data for the charts
   - Mock API endpoints structure
"""

# Example 2: Create an ecommerce product catalog
# ===============================================

example_2_description = """
Build an ecommerce product catalog with AI-generated product images:

1. Product Categories:
   - Electronics
   - Clothing
   - Home & Garden
   - Sports & Outdoors

2. For each category, generate 6 product images:
   - Electronics: "Professional laptop on desk, modern design, blue lighting"
   - Electronics: "Wireless headphones, premium design, metallic finish"
   - Clothing: "White professional t-shirt on mannequin, studio photography"
   - Clothing: "Blue jeans, laid flat, product photography, clean background"
   - Home: "Modern ceramic vase, white background, studio lighting"
   - Home: "Wooden cutting board with vegetables, food photography"
   - Sports: "Professional running shoes, side view, white background"
   - Sports: "Yoga mat rolled up, vibrant colors, studio photography"
   - (and so on...)

3. HTML template showing products in a grid layout

4. Generate image gallery preview showing all 18 product images
"""

# Example 3: Create gaming assets
# =================================

example_3_description = """
Create a simple 2D game with AI-generated assets:

1. Game: "Space Shooter" - shoot asteroids with your spaceship

2. Game Assets to generate:
   - Player spaceship: "Futuristic spaceship seen from above, blue and white, triangular shape, detailed"
   - Enemy spaceship: "Red alien spaceship, menacing design, spiky edges"
   - Asteroid variants (3 sizes):
     - Large: "Large asteroid, rocky surface, space background"
     - Medium: "Medium asteroid, detailed surface texture"
     - Small: "Small asteroid particle, glowing edges"
   - Explosion effect: "Bright explosion with particles, orange and yellow colors"
   - Bullet/projectile: "Blue energy bolt, glowing effect"
   - Space background: "Deep space scene with stars and nebula, dark blue and purple"

3. Game code:
   - Collision detection
   - Score system
   - Sound effects (using Web Audio API)
   - Touch/mouse controls

4. HTML5 Canvas implementation
"""

# Example 4: Documentation website with auto-generated diagrams
# ==============================================================

example_4_description = """
Create a technical documentation site with AI-generated visual content:

1. Main Pages:
   - Getting Started Guide
   - API Reference
   - Architecture Overview
   - Troubleshooting
   - FAQ

2. Generated Diagrams/Images:
   - System architecture diagram: "Technical system architecture diagram, blue and grey, showing microservices connected together"
   - Database schema visualization: "Database table schema diagram, ERD style, showing relationships between entities"
   - API flow diagram: "API request and response flow diagram, showing client, server, and database"
   - Network topology: "Network topology diagram, showing servers, load balancer, and connections"
   - Infrastructure overview: "Cloud infrastructure diagram, AWS style, showing different services"

3. Code examples with syntax highlighting

4. Dark theme optimized for code readability

5. Responsive design for all devices
"""

# Example 5: Portfolio/Resume with AI art
# ========================================

example_5_description = """
Create an interactive portfolio website with AI-generated artwork:

1. Portfolio Sections:
   - Hero section with AI generated abstract art background
   - Projects showcase (6 projects with generated preview images)
   - Skills section with icons
   - About me section with AI portrait
   - Contact section

2. Generated Images:
   - Hero background: "Abstract digital art, flowing colors, blue and purple gradients, modern style"
   - Project 1 preview: "Web development interface mockup, modern design, colorful"
   - Project 2 preview: "Mobile app interface, iOS style, clean and minimalist"
   - Project 3 preview: "Data visualization dashboard, colorful charts and graphs"
   - Project 4 preview: "E-commerce website mockup, product showcase"
   - Project 5 preview: "AI/ML application interface, tech concept"
   - Project 6 preview: "Game screenshot mockup, action scene"
   - Skills icons: "Python logo, JavaScript logo, React logo, Docker logo, etc"
   - About portrait: "Professional headshot, friendly expression, studio lighting"

3. Smooth scrolling animations

4. Dark mode / Light mode toggle
"""


def run_example():
    """
    Demonstrates how to use the auto_agent with image generation.
    """
    print("\n" + "="*70)
    print("Image Generator Tool - Auto Agent Integration Examples")
    print("="*70 + "\n")

    examples = [
        ("1", "Dashboard Web App", example_1_description),
        ("2", "E-commerce Catalog", example_2_description),
        ("3", "2D Game with Assets", example_3_description),
        ("4", "Documentation Site", example_4_description),
        ("5", "Portfolio Website", example_5_description),
    ]

    for num, title, desc in examples:
        print(f"\n{title}")
        print("-" * len(title))
        print(desc)
        print()

    print("\n" + "="*70)
    print("To run these examples, use:")
    print("="*70)
    print()
    print("python auto_agent.py \\")
    print('  --description "Create a professional modern dashboard..." \\')
    print('  --name "dashboard_with_images"')
    print()
    print("The auto_agent will:")
    print("  1. Detect that images are needed")
    print("  2. Call generate_image() for each required image")
    print("  3. Save images to: ./generated_images/")
    print("  4. Integrate the images into the project files")
    print("  5. Update HTML/CSS/React components to use the images")
    print()
    print("Available image generator tools:")
    print("  - generate_image(): Generate single image")
    print("  - generate_image_batch(): Generate multiple images at once")
    print("  - list_generated_images(): List all generated images")
    print("  - check_stablematrix_status(): Verify StableMatrix is running")
    print()
    print("Configuration in .env:")
    print("  - STABLEMATRIX_URL=http://192.168.1.217:7860")
    print("  - IMAGE_OUTPUT_DIR=generated_images")
    print()
    print("="*70 + "\n")


if __name__ == "__main__":
    run_example()

    # Note: To actually use with auto_agent, ensure:
    # 1. StableMatrix/WebUI is running at the URL in .env
    # 2. requirements.txt has 'requests' installed
    # 3. The image_generation_tools module is imported in the domains

    print("\nTo generate images manually, you can also use the tool directly:")
    print()
    print("from src.utils.domains.multimedia.image_generation_tools import ImageGeneratorTools")
    print("from src.utils.core.agent_logger import AgentLogger")
    print()
    print("logger = AgentLogger.create()")
    print("generator = ImageGeneratorTools(logger=logger)")
    print()
    print("# Generate single image")
    print('result = generator.generate_image("A beautiful sunset over mountains")')
    print("if result['ok']:")
    print(f"    print(f\"Image saved to: {{result['path']}}\")")
    print()
    print("# Generate multiple images")
    print('prompts = ["Mountain landscape", "Ocean waves", "Forest path"]')
    print("batch_result = generator.generate_image_batch(prompts=prompts)")
    print("print(f\"Generated {batch_result['total']} images\")")
    print()
    print("# Check StableMatrix status")
    print("status = generator.check_stablematrix_status()")
    print("print(f\"StableMatrix status: {status['status']}\")")
    print()
