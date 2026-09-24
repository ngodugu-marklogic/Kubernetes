FROM node:24-alpine AS development
WORKDIR /app

COPY package*.json ./

EXPOSE 4200

CMD ["npm", "run", "dev"]

FROM node:24-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
