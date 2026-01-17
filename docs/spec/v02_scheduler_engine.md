# Spec: Motor de Agendamento (The Scheduler)

## 1. Objetivo
Gerenciar a execução assíncrona de tarefas, como a escrita completa de posts e a publicação automática no WordPress, respeitando os limites de tempo e créditos de cada usuário.

## 2. Funcionamento Técnico (SDD Workflow)
O Scheduler opera como um processo independente (`python scheduler.py`) que executa um loop infinito:
1. **Varredura**: O sistema consulta a tabela `ContentIdea` em busca de registros com `status='pending'`.
2. **Priorização**: Ordena as tarefas pela data de criação ou horário agendado.
3. **Processamento (The Writing Flow)**:
    - **IA Expansion**: Transforma o título/insight em um artigo completo de 600+ palavras.
    - **Image Handling**: (Opcional) Gera ou busca uma imagem de destaque.
    - **WP Injection**: Envia os dados formatados para a REST API do WordPress via `wordpress_service`.
4. **Finalização**: 
    - Atualiza a ideia para `is_posted=True`.
    - Registra o sucesso ou falha na tabela `PostLog`.

## 3. Regras de Resiliência (Policies)
- **Retry Logic**: Caso a API da Groq ou do WordPress falhe, o status deve retornar para `pending` (ou `error`) com um contador de tentativas, evitando loops infinitos em posts corrompidos.
- **Contexto de App**: O script deve sempre rodar dentro do `with app.app_context()` para acessar o banco de dados.
- **Isolamento**: Falhas em um post de um usuário não podem interromper a fila de outros usuários.

## 4. Definição de Pronto (Definition of Done)
- [ ] O script `scheduler.py` roda em um terminal separado sem encerrar sozinho.
- [ ] Posts marcados como "Postar agora" (status `pending`) são publicados em menos de 2 minutos.
- [ ] O usuário consegue ver o histórico de sucesso/erro no "Relatório de Postagens".

## 5. Comandos de Execução
- **Local**: `python scheduler.py`
- **Produção (PM2)**: `pm2 start scheduler.py --name "autoblog-worker" --interpreter python3`