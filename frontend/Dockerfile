FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy application code
COPY . .

# Build
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
