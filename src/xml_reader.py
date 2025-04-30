from lxml import etree
import pandas as pd
import io

NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"

def extrair_dados_xmls(arquivos_xml):
    registros = []
    arquivos_dict = {}

    for file in arquivos_xml:
        try:
            # Parse do arquivo
            tree = etree.parse(file)
            root = tree.getroot()

            # Salvar conteúdo do arquivo
            arquivos_dict[file.name] = file.getvalue()

            infNFe = root.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
            if infNFe is None:
                continue

            emit = root.find(".//{http://www.portalfiscal.inf.br/nfe}emit")
            if emit is not None:
                cnpj_emissor = emit.findtext("{http://www.portalfiscal.inf.br/nfe}CNPJ", default="")
                fornecedor = emit.findtext("{http://www.portalfiscal.inf.br/nfe}xNome", default="")
            else:
                cnpj_emissor = ""
                fornecedor = ""

            chave = infNFe.get("Id", "").replace("NFe", "")
            valor_total = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}vNF", default="0")
            cfop_atual = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}CFOP", default="")
            credito_icms = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}vICMS", default="0")

            # Nova extração da data da nota
            data_emissao = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}dhEmi", default="")
            if not data_emissao:
                data_emissao = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}dEmi", default="")

            # Complemento: CNPJ + Razão Social + Número da Nota
            numero_nota = root.findtext(".//{http://www.portalfiscal.inf.br/nfe}nNF", default="")
            complemento = f"{cnpj_emissor} {fornecedor} {numero_nota}"

            registros.append({
                "chave": chave,
                "tipo": "NFe",
                "fornecedor": fornecedor,
                "cnpj_emissor": cnpj_emissor,
                "valor_total": float(valor_total),
                "cfop_atual": cfop_atual,
                "credito_icms": float(credito_icms),
                "data_nota": data_emissao,
                "complemento": complemento
            })

        except Exception as e:
            print(f"Erro ao processar {file.name}: {e}")
            continue

    df = pd.DataFrame(registros)
    return df, arquivos_dict
