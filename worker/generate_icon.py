import os
from PIL import Image, ImageDraw

def generate_icon():
    os.makedirs("assets", exist_ok=True)
    size = 256
    
    # Create a solid blue image with some padding
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a circle touching the absolute edges (no padding) so it appears large in taskbar
    padding = 0
    draw.ellipse((padding, padding, size - padding, size - padding), fill=(30, 144, 255, 255))
    
    # Save as PNG
    img.save("assets/icon.png", format="PNG")
    
    # Save as ICO (multi-size)
    img.save("assets/icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("Generated high-res icon.png and icon.ico!")

if __name__ == "__main__":
    generate_icon()
