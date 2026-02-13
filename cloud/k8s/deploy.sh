#!/bin/bash
set -e

echo "Deploying Virtual Lab to Kubernetes..."

# Create namespace
kubectl apply -f namespace.yaml

# Create secrets (edit secrets.yaml with real base64 values first!)
kubectl apply -f secrets.yaml

# Deploy infrastructure
kubectl apply -f postgres/
kubectl apply -f redis/

echo "Waiting for PostgreSQL to be ready..."
kubectl -n virtuallab wait --for=condition=ready pod -l app=postgres --timeout=120s

echo "Waiting for Redis to be ready..."
kubectl -n virtuallab wait --for=condition=ready pod -l app=redis --timeout=60s

# Deploy application
kubectl apply -f backend/
kubectl apply -f frontend/

echo "Waiting for backend to be ready..."
kubectl -n virtuallab wait --for=condition=ready pod -l app=backend --timeout=120s

# Deploy ingress
kubectl apply -f ingress.yaml

echo "Deployment complete!"
echo "Run 'kubectl -n virtuallab get pods' to check status."
