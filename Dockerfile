# Usa uma imagem leve do Python
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para o scraper
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de requisitos e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Expõe a porta que o Flask usa
EXPOSE 5000

# Comando para rodar a aplicação
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers 1"]