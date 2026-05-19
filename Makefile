.PHONY: build-frontend build build-wheel build-sdist publish clean

build-frontend:
	cd frontend && npm ci && npm run build

build: build-frontend
	uv build

build-wheel: build-frontend
	uv build --wheel

build-sdist: build-frontend
	uv build --sdist

publish: build
	uv publish

clean:
	rm -rf build dist *.egg-info src/*.egg-info
