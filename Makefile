# Image name and tag
IMAGE_NAME := amqtt
IMAGE_TAG := latest
VERSION_TAG := 0.11.0
REGISTRY := amqtt/$(IMAGE_NAME)

# Platforms to build for
PLATFORMS := linux/amd64,linux/arm64

# Default target
.PHONY: all
all: build

# Build multi-platform image
.PHONY: build
build:
	docker buildx build \
		--platform $(PLATFORMS) \
		--tag $(REGISTRY):$(IMAGE_TAG) \
		--tag $(REGISTRY):$(VERSION_TAG) \
		--file Dockerfile \
		--push .

# Optional: build without pushing (for local testing)
.PHONY: build-local
build-local:
	docker buildx build \
		--tag $(REGISTRY):$(IMAGE_TAG) \
		--tag $(REGISTRY):$(VERSION_TAG) \
		--file Dockerfile \
		--load .

# Create builder if not exists
.PHONY: init
init:
	docker buildx create --use --name multi-builder || true
	docker buildx inspect --bootstrap