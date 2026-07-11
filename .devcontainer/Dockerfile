# Use the full-featured LaTeX development container as the base image
FROM qmcgaw/latexdevcontainer:latest-full

# Update the package list and install necessary utility packages
RUN apt-get update && \
    # DEBIAN_FRONTEND=noninteractive: Suppresses interactive prompts during installation
    # -y: Automatically answers 'yes' to all confirmation prompts
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    # Required for PostScript/PDF processing and certain LaTeX packages
    ghostscript \
    # Provides OpenGL GLX libraries (often needed for GUI/graphics tools)
    libgl1-mesa-glx \
    # Clean up the apt cache to keep the Docker image size as small as possible
    && rm -rf /var/lib/apt/lists/*