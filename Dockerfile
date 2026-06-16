# Frontend build → static nginx image.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
# VITE_BASE defaults to './' (see vite.config.ts) so asset URLs are emitted
# relative to index.html and runtime API URLs derive from document.baseURI
# (src/lib/apiBase.ts). One image works at /, /app/, or any prefix.
# VITE_API_BASE is intentionally left empty so the runtime derivation kicks in.
ARG VITE_ENGINE=agent
ARG VITE_BASE=./
ENV VITE_ENGINE=$VITE_ENGINE
ENV VITE_BASE=$VITE_BASE
ENV VITE_API_BASE=
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
