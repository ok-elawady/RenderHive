FROM python:3.11-slim

WORKDIR /app

# Build dependencies removed since we install pre-compiled wheels.
# We accept a USE_CUDA build argument (default 0) to determine which wheel to download.
ARG USE_CUDA=0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Conditionally install CUDA or CPU wheel during image build
# If CUDA, also install the necessary runtime libraries since the slim base image lacks them
RUN if [ "$USE_CUDA" = "1" ]; then \
      pip install --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 nvidia-cuda-runtime-cu12 nvidia-cublas-cu12; \
    else \
      pip install --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu; \
    fi

# Set the library path so libllama.so can find the pip-installed CUDA runtime libraries
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:${LD_LIBRARY_PATH}

COPY . .

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose the API port
EXPOSE 8001

# Run the FastAPI app
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
