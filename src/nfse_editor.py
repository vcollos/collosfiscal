# src/nfse_editor.py

from lxml import etree
import io
import zipfile

def alterar_natureza_e_gerar_zip(arquivos_dict, chaves_para_alterar, nova_natureza):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for nome_arquivo, conteudo in arquivos_dict.items():
            try:
                tree = etree.parse(io.BytesIO(conteudo))
                root = tree.getroot()

                infNfse = root.find(".//InfNfse")
                if infNfse is None:
                    continue

                chave = infNfse.findtext("Numero", default="")
                if chave not in chaves_para_alterar:
                    zipf.writestr(nome_arquivo, conteudo)
                    continue

                natureza = root.find(".//NaturezaOperacao")
                if natureza is not None:
                    natureza.text = nova_natureza

                buffer = io.BytesIO()
                tree.write(buffer, encoding="utf-8", xml_declaration=True, pretty_print=False)
                zipf.writestr(nome_arquivo, buffer.getvalue())

            except Exception as e:
                print(f"Erro ao processar {nome_arquivo}: {e}")
                continue

    zip_buffer.seek(0)
    return zip_buffer