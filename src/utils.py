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

    "Transferência - Dentro do Estado": "5152",
    "Transferência - Fora do Estado": "6152",

    "Bonificação / Brinde - Dentro do Estado": "5910",
    "Bonificação / Brinde - Fora do Estado": "6910",

    "Doação - Dentro do Estado": "5910",
    "Doação - Fora do Estado": "6910",

    "Demonstração - Dentro do Estado": "5911",
    "Demonstração - Fora do Estado": "6911",

    "Remessa para Conserto - Dentro do Estado": "5901",
    "Remessa para Conserto - Fora do Estado": "6901",

    "Retorno de Conserto - Dentro do Estado": "5902",
    "Retorno de Conserto - Fora do Estado": "6902",

    "Remessa para Industrialização - Dentro do Estado": "5903",
    "Remessa para Industrialização - Fora do Estado": "6903",

    "Retorno de Industrialização - Dentro do Estado": "5904",
    "Retorno de Industrialização - Fora do Estado": "6904",
}

def limpar_texto(texto):
    """
    Função utilitária para limpar espaços e normalizar textos extraídos de XML.
    """
    if texto:
        return texto.strip()
    return texto
