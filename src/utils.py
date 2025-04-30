# src/utils.py
from dotenv import load_dotenv
import os

load_dotenv()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
DEBUG = os.getenv("DEBUG", "False") == "True"

# Mapa dos tipos de operação para seus respectivos CFOPs
CFOP_MAP = {
    "Consumo - Dentro do Estado": "1556",
    "Consumo - Fora do Estado": "2556",
    "Revenda - Dentro do Estado": "1102",
    "Revenda - Fora do Estado": "2102",
    "Ativo Imobilizado - Dentro do Estado": "1551",
    "Ativo Imobilizado - Fora do Estado": "2551",
    "Serviço - Dentro do Estado": "1126",
    "Serviço - Fora do Estado": "2126",
}

def limpar_texto(texto):
    """
    Função utilitária para limpar espaços e normalizar textos extraídos de XML.
    """
    if texto:
        return texto.strip()
    return texto