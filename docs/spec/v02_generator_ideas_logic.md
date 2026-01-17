# Spec: Gerador de Ideias (Brainstorm IA)

## 1. Objetivo
Automatizar a criação de pautas (títulos) para posts de blog utilizando Inteligência Artificial, garantindo que cada sugestão esteja vinculada a um site específico e respeite as diretrizes temáticas do usuário.

## 2. Fluxo de Operação (SDD Workflow)
1. **Entrada**: O usuário acessa a rota `/ideas` e submete o formulário de geração com um `site_id`.
2. **Contextualização**: O sistema carrega os metadados do Blog (Nome, Temas Macro, Fuso Horário).
3. **Chamada de IA**: 
    - Provedor: Groq (Llama 3).
    - Prompt: Instrução para gerar 5 títulos baseados nos Temas Macro.
4. **Persistência**: 
    - Cada título é limpo e validado.
    - É criada uma instância de `ContentIdea` com o `blog_id` obrigatório.
    - Status inicial definido como `draft`.

## 3. Regras de Integridade (Constraints)
- **Vínculo de Blog**: É proibido criar uma `ContentIdea` com `blog_id = NULL`. O sistema deve realizar o `rollback` da transação caso o ID seja perdido.
- **Segurança de Créditos**: Cada geração de 5 ideias consome o equivalente a 1 crédito (ou conforme regra de negócio definida no `credit_service`).
- **Sanitização**: Títulos gerados com aspas ou numerações da IA (ex: "1. Título") devem ser limpos antes de salvar.

## 4. Definição de Pronto (Definition of Done)
- [ ] O usuário consegue visualizar as novas 5 ideias na tabela imediatamente após o refresh.
- [ ] O banco de dados não apresenta erros de `IntegrityError` durante o processo.
- [ ] O log de uso da API (`ApiUsage`) é registrado corretamente para controle de custos.

## 5. Manutenção
Caso o gerador falhe:
1. Verificar conexão com a API Key da Groq no arquivo `.env`.
2. Rodar o script `manutencao.py` para limpar possíveis registros órfãos.
3. Verificar se o site selecionado ainda possui credenciais WordPress válidas.