# Spec: Correção de Integridade de Conteúdo e Vínculo de Blog

## 1. Problema (Contexto)
Ocorreu um `sqlalchemy.exc.IntegrityError`. O sistema tentou atualizar registros na tabela `content_idea` deixando a coluna `blog_id` como `NULL`. Como o banco de dados exige esse vínculo (NotNullViolation), a operação falhou.

## 2. Causa Raiz
No arquivo `content_service.py`, a função `generate_ideas_logic` ou o processamento de retorno da IA não está garantindo que o objeto `Blog` e seu `ID` sejam propagados corretamente para cada instância de `ContentIdea` criada.

## 3. Alterações Necessárias

### A. services/content_service.py
- **Função `generate_ideas_logic(blog)`**:
    - Deve validar se `blog.id` existe antes de iniciar.
    - Na iteração de criação das ideias (loop), o campo `blog_id` deve ser explicitamente definido como `blog.id`.
    - Adicionar um `db.session.flush()` antes do commit para capturar erros de integridade precocemente.

### B. routes/content.py
- **Rota `/generate-ideas`**:
    - Garantir que o `site_id` vindo do formulário seja validado.
    - Passar o objeto `blog` completo para o serviço, e não apenas o ID, para manter a consistência do contexto.

## 4. Verificação de Sucesso (Definition of Done)
1. Executar a geração de ideias para o "Site A".
2. Verificar no banco se todas as ideias geradas possuem o `blog_id` correspondente ao "Site A".
3. Tentar gerar ideias sem selecionar um site e garantir que o sistema barrou a operação antes de chegar ao banco.