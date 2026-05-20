# Capital web — multi-stage build.
# Stage 1 compiles the static assets; stage 2 serves them with nginx.
# (Per the deployment plan, production may instead copy `dist/` into the
# shared Caddy image — this standalone image keeps `web` runnable on its own.)

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback: route every path to index.html so client-side routing works.
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
