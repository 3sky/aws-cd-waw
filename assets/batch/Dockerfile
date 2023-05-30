# f*k Dockerhub and rate limits
FROM public.ecr.aws/ubuntu/ubuntu:20.04_stable

ENV TZ=Europe/Warsaw
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    libmagick++-dev \
    ghostscript \
    ttf-mscorefonts-installer \
    libfreetype6-dev \
    gsfonts \
    libmagickwand-dev \
    imagemagick \
    && sed -i '/<policy domain="path" rights="none" pattern="@\*"/d' /etc/ImageMagick-6/policy.xml \
    && sed -i 's/rights="none" pattern="PDF"/rights="read | write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml \
    && fc-cache -f \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY code/requirements.txt .

# Install the application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY code/* ./

# Define the command to run the application
ENTRYPOINT [ "python3", "locate.py" ]