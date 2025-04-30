# Usa imagem oficial do Python 3.11
FROM python:3.11-slim

# Define diretório de trabalho dentro do container
WORKDIR /app

# Copia apenas o requirements e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto
COPY . .

# Expõe a porta usada internamente pela aplicação
EXPOSE 8501

# Comando para iniciar a aplicação
CMD ["streamlit", "run", "main.py"]