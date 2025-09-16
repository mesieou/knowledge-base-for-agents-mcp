FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
USER node
EXPOSE 8080
CMD ["node", "dist/server.js"]
