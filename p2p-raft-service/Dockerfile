FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all source code
COPY proto /app/proto
COPY api /app/api
COPY models /app/models
COPY raft /app/raft
COPY replication /app/replication
COPY config.py /app/config.py
COPY grpc_server.py /app/grpc_server.py
COPY main.py /app/main.py

# Create directories for generated protobuf files
RUN mkdir -p /app/p2p_pb2 /app/ehr_pb2

# Create __init__.py files
RUN touch /app/p2p_pb2/__init__.py /app/ehr_pb2/__init__.py

# Generate protobuf files
RUN python -m grpc_tools.protoc \
    -I proto \
    --python_out=p2p_pb2 \
    --grpc_python_out=p2p_pb2 \
    proto/p2p.proto

RUN python -m grpc_tools.protoc \
    -I proto \
    --python_out=ehr_pb2 \
    --grpc_python_out=ehr_pb2 \
    proto/ehr_service.proto

# Fix imports: Replace absolute imports with relative imports in generated files
RUN sed -i 's/^import p2p_pb2 as/from . import p2p_pb2 as/g' p2p_pb2/p2p_pb2_grpc.py; exit 0
RUN sed -i 's/^import ehr_service_pb2 as/from . import ehr_service_pb2 as/g' ehr_pb2/ehr_service_pb2_grpc.py; exit 0

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
