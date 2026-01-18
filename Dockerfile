# Usa uma imagem leve do Python
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema + SUPERVISOR
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de requisitos e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Copia o arquivo de configuração do supervisor que vamos criar abaixo
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expõe a porta que o Flask usa
EXPOSE 5000

# Comando para rodar a aplicação
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers 1"]

# O comando principal agora é o supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]