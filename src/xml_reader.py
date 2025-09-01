from lxml import etree
import pandas as pd
import io

NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"

def extrair_dados_xmls(arquivos_xml, progress_callback=None):
    """
    Extrai dados principais das NF-e e também os itens de cada nota.

    Retorna:
      - df: DataFrame com registros por nota (chave, fornecedor, cnpj_emissor, valor_total, cfop_atual, ...)
      - arquivos_dict: mapeamento nome_arquivo -> conteúdo_bytes (compatível com uso anterior)
      - itens_por_chave: mapeamento chave -> lista de itens (cada item é dict com campos como nItem, cProd, xProd, qCom, vProd, cfop)
    """
    registros = []
    arquivos_dict = {}
    itens_por_chave = {}

    total = len(arquivos_xml)
    for idx, file in enumerate(arquivos_xml, start=1):
        try:
            # Parse do arquivo
            tree = etree.parse(file)
            root = tree.getroot()

            # Salvar conteúdo do arquivo (mantendo compatibilidade: nome -> bytes)
            try:
                arquivos_dict[file.name] = file.getvalue()
            except Exception:
                # Se o objeto não tiver getvalue (por alguma razão), ler do começo
                file.seek(0)
                arquivos_dict[file.name] = file.read()

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

            # Extrair itens (det)
            itens = []
            for det in root.findall(".//{http://www.portalfiscal.inf.br/nfe}det"):
                # nItem normalmente é atributo do det
                nItem = det.get("nItem", "")
                prod = det.find("{http://www.portalfiscal.inf.br/nfe}prod")
                if prod is None:
                    continue
                cProd = prod.findtext("{http://www.portalfiscal.inf.br/nfe}cProd", default="")
                xProd = prod.findtext("{http://www.portalfiscal.inf.br/nfe}xProd", default="")
                qCom = prod.findtext("{http://www.portalfiscal.inf.br/nfe}qCom", default="")
                vProd = prod.findtext("{http://www.portalfiscal.inf.br/nfe}vProd", default="")
                cfop_item = prod.findtext("{http://www.portalfiscal.inf.br/nfe}CFOP", default="")

                itens.append({
                    "nItem": nItem,
                    "cProd": cProd,
                    "xProd": xProd,
                    "qCom": qCom,
                    "vProd": vProd,
                    "cfop": cfop_item
                })

            # Salva itens por chave
            itens_por_chave[chave] = itens

            registros.append({
                "chave": chave,
                "tipo": "NFe",
                "fornecedor": fornecedor,
                "cnpj_emissor": cnpj_emissor,
                "valor_total": float(valor_total) if valor_total not in (None, "") else 0.0,
                "cfop_atual": cfop_atual,
                "credito_icms": float(credito_icms) if credito_icms not in (None, "") else 0.0,
                "data_nota": data_emissao,
                "complemento": complemento,
                "nNF": numero_nota
            })

            # Atualiza progresso, se callback fornecido
            if callable(progress_callback):
                try:
                    progress_callback(idx, total, getattr(file, 'name', None))
                except Exception:
                    pass

        except Exception as e:
            print(f"Erro ao processar {getattr(file, 'name', str(file))}: {e}")
            if callable(progress_callback):
                try:
                    progress_callback(idx, total, getattr(file, 'name', None))
                except Exception:
                    pass
            continue

    df = pd.DataFrame(registros)
    return df, arquivos_dict, itens_por_chave
