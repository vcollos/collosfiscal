# Deploy & Observabilidade

Modos de Deploy
- Local (desenvolvimento): `streamlit run app.py`
- Servidor próprio: executar via serviço (systemd) apontando para virtualenv e app
- Cloud (ex.: Streamlit Cloud): configurar secrets/banco e rodar `app.py`

Boas práticas
- Manter variáveis de ambiente via arquivo de serviço/secret store
- Não comitar `.env` com credenciais reais
- Evitar dependências desnecessárias no sistema

Monitoração
- Logs do serviço/Streamlit
- Métricas operacionais (número de notas, tempo de processamento) podem ser adicionadas conforme necessidade

