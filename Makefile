build-frontend:
	cd frontend && npm install && npm run build

build: build-frontend
	uv build

publish: build
	uv publish
