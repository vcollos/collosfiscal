# src/xml_editor.py

from lxml import etree
import io
import zipfile

NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
NSMAP = {None: NFE_NAMESPACE}  # sem prefixo (evita ns0)

def alterar_cfops_e_gerar_zip(arquivos_dict, chaves_para_alterar, novo_cfop):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for nome_arquivo, conteudo in arquivos_dict.items():
            try:
                tree = etree.parse(io.BytesIO(conteudo))
                root = tree.getroot()

                infNFe = root.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
                if infNFe is None:
                    continue

                chave = infNFe.get("Id", "").replace("NFe", "")
                if chave not in chaves_para_alterar:
                    zipf.writestr(nome_arquivo, conteudo)
                    continue

                # Altera todos os CFOPs
                for cfop in root.findall(".//{http://www.portalfiscal.inf.br/nfe}CFOP"):
                    cfop.text = novo_cfop

                buffer = io.BytesIO()
                tree.write(buffer, encoding="utf-8", xml_declaration=True, pretty_print=False)
                zipf.writestr(nome_arquivo, buffer.getvalue())

            except Exception as e:
                print(f"Erro ao processar {nome_arquivo}: {e}")
                continue

    zip_buffer.seek(0)
    return zip_buffer