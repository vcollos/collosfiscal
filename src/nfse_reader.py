from lxml import etree
import pandas as pd
import io

def extrair_dados_nfses_xmls(arquivos_xml):
    registros = []
    arquivos_dict = {}

    for file in arquivos_xml:
        try:
            tree = etree.parse(file)
            root = tree.getroot()

            arquivos_dict[file.name] = file.getvalue()

            infNfse = root.find(".//InfNfse")
            if infNfse is None:
                continue

            prestador = root.find(".//PrestadorServico/IdentificacaoPrestador")
            cnpj_emissor = prestador.findtext("Cnpj", default="") if prestador is not None else ""

            numero_nfse = infNfse.findtext("Numero", default="")
            fornecedor = root.findtext(".//PrestadorServico/RazaoSocial", default="")
            valor_total = root.findtext(".//Valores/ValorServicos", default="0")
            cfop_atual = ""
            credito_icms = 0

            # Nova extração da data da nota
            data_emissao = infNfse.findtext("DataEmissao", default="")

            # Complemento: CNPJ + Razão Social + Número da Nota
            complemento = f"{cnpj_emissor} {fornecedor} {numero_nfse}"

            registros.append({
                "chave": numero_nfse,
                "tipo": "NFSe",
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
