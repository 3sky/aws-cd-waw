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

ENV AWS_ACCESS_KEY_ID="ASIAQVXM6MINTG27R4OA"
ENV AWS_SECRET_ACCESS_KEY="+LHGFUX6fyOcO6RkRLn/xX7Z+4jkxNCL2BovbR71"
ENV AWS_SESSION_TOKEN="IQoJb3JpZ2luX2VjEDsaCWV1LXdlc3QtMSJIMEYCIQDlSzKaZsY4Cr8bOJTEkYhC1MUWhrCWeNT4+zYy0tXtcQIhAKgpE/opW0X7E4KiUKjDj8AMeuQFLqNrOOti4mI6f2dWKvcCCHQQABoMMDQ2NjY3ODE3NDk5IgzsKm6Iby6UV9QB4koq1AJp8cTS6Y489HHCC1EZk+pK8a3A6qoAVyn2x0gWbtOPyyhoQtRVj5KgQ+T2le7Yv7nfX5NPMzwN8/T+XaSAo/kf1jfeb+hhXJA2B/iD73gnk6HYNSk/oDdPBk/CXx/P7u/yOFG0zDVdbo7FYjuwdVbH3eacEEcBHaohiL0+FOXt8Qpt6wXWOM2jXiYgF+zSrfEP+L6mCNE8ShIey3Chy8Tnc+BVSzoLiOnIXv1BbnYdKD5ABcAcPbkGWp07evZ+wOpfktw6Z5EMHQMP8pCsM8PI3CDz9TCJGwwAcG+5knnYl7tFaNQpBatUZTEwBY21tDeFN65+/ocpmT5B2W15rBR9QQaO4sh81uBs076ZIe0t9itzG+tWQyksjjCU8fJ/JKxgxLHB2Y+3ibintz4hVFskNgqk+sgHVEB3n4G8Tldp0UMzJzIs4QC8RhdK+zh3Bmjfx6+rMMD70aMGOqYBQYHrlWlYGWxk2SOhZpfWR0wTvPY73cHx7WuWVV9X6J6J0WoG79me3I6QndLqwMiJov2Qm2F2gofiSU0INEPw24z61sIuBjEQIM3kl8snCHRk/DlZDazorVxwt7ONpbCLgUq5DsWm8Cd0p66i0Gs/GTzCd+Mg95cGC9cWngCeK2HGbtsQROZHNIZYF80xqqgPbVQ2aY3Vuugtw/cDfWv9x0xJu0Tq4A=="

# Define the command to run the application
ENTRYPOINT [ "python3", "locate.py" ]