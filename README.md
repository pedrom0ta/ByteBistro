# ByteBistro

## Arquitetura e Documentação Técnica

Consulte o [índice técnico do ByteBistro](docs/architecture/README.md) para o System Design, os diagramas editáveis e as decisões arquiteturais.

## Executar o cardápio digital

O cliente web Django está em [client](client/README.md). Ele permite montar o carrinho, pedir na mesa ou por delivery e acompanhar o pedido. A demonstração usa um catálogo local, SQLite e verificação por código no terminal.

```powershell
cd client
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Abra [o ByteBistro local](http://127.0.0.1:8000/). O [guia do cliente](client/README.md) descreve as telas, testes, atualização de status e integração futura com GraphQL.

O [painel do restaurante](http://127.0.0.1:8000/painel/) usa os mesmos pedidos e produtos. Crie a primeira conta com `python manage.py createsuperuser` a partir de `client`. O [guia de operação](client/README.md#painel-do-restaurante) explica perfis, recebimento, cozinha e relatórios.

## Sistema de Cardápio Digital e Gerenciamento de Pedidos

**PROFESSOR**  
Levi Costa

**INTEGRANTES**  
Pedro Antonio, Tauan Gomes, Augusto Fagner

---

# O DOMÍNIO

## Por que Restaurantes?

- **Necessidade Real:** Digitalização de cardápios.
- **Fluxo Claro:** Organização exata de pedidos.
- **Adequação:** Perfeito para sistemas distribuídos.

---

# O DESAFIO

## O que o ByteBistro resolve?

### Desorganização
Cardápios físicos e desatualizados.

### Atrasos
Lentidão no registro de pedidos.

### Descentralização
Dados fragmentados e perdidos.

---

# VISÃO GERAL

## Fluxo do Negócio

**Restaurante → Menu → Produtos → Carrinho → Pedido**

### 1. Restaurante

É a base do sistema. O restaurante representa o estabelecimento que utiliza o ByteBistro para organizar seu cardápio e gerenciar seus pedidos.

### 2. Menu

O restaurante possui um menu, que organiza a apresentação dos produtos disponíveis para os clientes.

### 3. Produtos

Dentro do menu ficam os produtos oferecidos pelo restaurante, contendo informações como nome, descrição e preço.

### 4. Carrinho

O cliente seleciona os produtos que deseja e os adiciona ao carrinho. Nessa etapa, os itens escolhidos são organizados antes da finalização.

### 5. Pedido

Após revisar o carrinho, o cliente confirma a compra. O sistema transforma os itens selecionados em um pedido, que é registrado no Backend e armazenado no banco de dados.

---

# DIFERENCIAL

## Proposta de Valor

### Centralização

- Controle total do fluxo gastronômico.
- Organização imediata do cardápio.
- Gestão simplificada de produtos.
- Integração fluida até o pedido final.

---

# SYSTEM DESIGN — ARQUITETURA PROPOSTA

## Visão Geral da Arquitetura

> **O CLIENTE NÃO ACESSA O BANCO DIRETAMENTE**

**Cliente**  
*(Django + Requests)*

↓ HTTP / GraphQL ↓

**Node.js + TypeScript**

↓

**Apollo Server + Resolvers**

↓

**Prisma ORM**

↓

**PostgreSQL**

---

## Diagrama Conceitual

```text
┌──────────────────────────┐
│         CLIENTE          │
│                          │
│          Django          │
│         Requests         │
└────────────┬─────────────┘
             │
             │ HTTP / GraphQL
             ▼
┌──────────────────────────┐
│       CONTAINER          │
│                          │
│   Node.js + TypeScript   │
│      Apollo Server       │
│        Resolvers         │
└────────────┬─────────────┘
             │
             │ Prisma ORM
             ▼
┌──────────────────────────┐
│       PERSISTÊNCIA       │
│                          │
│       PostgreSQL         │
└──────────────────────────┘

              Docker
      ─────────────────────
      Gerenciamento dos
      ambientes e serviços
```
---

# ARQUITETURA

## Modelagem e Responsabilidades

| CLIENTE | BACKEND | BANCO |
|---|---|---|
| Exibirá interface gráfica. | Recebe requisições HTTP. | Armazena informações. |
| Interagirá com usuário. | Processa regras de negócio. | Garante persistência. |
| Solicitará operações à API. | Valida dados e acessa banco. | Acessado via Prisma ORM. |

---

# PROTOCOLOS

## Comunicação do Sistema

> **GRAPHQL NÃO É BANCO DE DADOS.**

**Cliente**

↓ HTTP ↓

**GraphQL (API)**

↓ JSON ↓

**Backend**

↓ Prisma ↓

**Banco de Dados**

- **HTTP:** Protocolo de transporte.
- **GraphQL:** Tecnologia da API (Consultas/Mutações).
- **JSON:** Formato de troca de dados.

---

# ARQUITETURA BACKEND

## Monólito Modular vs Microsserviços

### ARQUITETURA INICIAL

**Monólito Modular**

Aplicação única organizada internamente por módulos.

Separar cliente e backend NÃO cria microsserviços.  
O backend inteiro roda no mesmo processo.

### PROPOSTA DE EVOLUÇÃO

**Microsserviços**

Serviços independentes, separados por rede.

Permite escalar módulos específicos individualmente.

---

# ARMAZENAMENTO

## Banco de Dados e Persistência

### PROPOSTA

**PostgreSQL**

Banco de dados relacional em rede.

**Solução:** Permite que múltiplas instâncias acessem a mesma fonte da verdade.

---

# EVOLUÇÃO DE INFRAESTRUTURA

## Balanceamento de Carga

### PROPOSTA ARQUITETURA

**Usuários**

↓

**Load Balancer (Distribuidor)**

↓

**Instância 1 | Instância 2 | Instância 3**

↓

**Banco de Dados Compartilhado (Nuvem)**

---

# SEGURANÇA

## Controle de Acesso

### Autenticação

**"Quem é você?"**

Verifica a identidade do usuário (ex: login com email e senha).

### Autorização

**"O que você pode fazer?"**

Define as permissões após o login (ex: Cliente vs Gerente).

---

# PROTEÇÃO

## Gestão de Segredos e Tokens

### Senhas
Nunca armazenadas em texto puro (Hashes).

### Tokens JWT
Credencial temporária após autenticação.

### Variáveis de Ambiente
Dados sensíveis fora do código-fonte.

### Regra de Ouro

> **O arquivo .env NUNCA sobe para o GitHub.**

---

# PRINCÍPIO DE SEGURANÇA

## "Nunca confie no cliente"

### O que NÃO fazer

Cliente envia:

```text
{ Produto: "X", Preço: 0,01 }
```

O backend aceita e registra o pedido por 1 centavo. O restaurante toma prejuízo por adulteração.

### O fluxo correto

**1.** Cliente envia apenas o ID do produto.

**2.** Backend consulta preço real no banco.

**3.** Backend calcula valor oficial.

**4.** Backend registra pedido seguro.

---

# CAPACIDADE

## Escalabilidade

Capacidade do sistema de suportar o aumento de usuários e requisições sem degradação significativa do serviço.

### Horizontal (Scale Out)

O ByteBistro utilizará **escalabilidade horizontal**, adicionando novas instâncias da aplicação conforme a demanda aumenta.

Em vez de aumentar os recursos de uma única máquina, novas instâncias são adicionadas para dividir a carga entre os servidores.

```text
                 Usuários
                     │
                     ▼
              Load Balancer
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Instância 1       Instância 2      Instância 3
          │          │          │
          └──────────┼──────────┘
                     ▼
             Banco PostgreSQL.
```

---

# EVOLUÇÃO

## Gerenciamento de Tráfego Automático

### PROPOSTA DE ARQUITETURA

**Load Balancer**

Distribui requisições uniformemente entre instâncias, evitando sobrecarga em um único nó.

### Auto Scaling

**Pico de acesso?** Cria novas instâncias.

**Baixo acesso?** Desliga instâncias para economizar.

---

# ANÁLISE CRÍTICA

## A barreira da Escalabilidade

### PROPOSTA

**LB + instâncias + PostgreSQL**

Desacoplar o banco para a rede. Múltiplas instâncias compartilham a mesma base de dados real.

---

# RESILIÊNCIA

## Tolerância a Falhas

Capacidade do sistema operar ou degradar graciosamente quando componentes quebram.

### Instância Cai
Tráfego redirecionado a nós saudáveis.

### Falha de Conexão
Tentar reconectar automaticamente.

### Timeout
Cancelar e notifica o usuário.

---

# PADRÕES DE RESILIÊNCIA

## Recuperação e Proteção

### Retry (Tentar Novamente)

Repetir uma operação que falhou por problema de rede passageiro antes de acusar erro final.

### Circuit Breaker (Disjuntor)

Cortar chamadas para um serviço já caído para não sobrecarregá-lo e falhar rápido (Fail Fast).

---

# PROCESSAMENTO ASSÍNCRONO

## Filas de Mensagens e DLQ

### PROPOSTA EVOLUTIVA

A DLQ guarda tarefas que falharam repetidamente para análise manual.

**API Recebe Pedido**

↓

**Fila (Queue)**

↓

**Processamento**

↓

**Falha Crítica?**

↓

**DLQ (Dead Letter Queue)**

---

# CONTINUIDADE DO NEGÓCIO

## Prevenção de Desastres

### Backup

Cópia regular dos dados.

### Estratégia exige:

- Frequência (diário/hora).
- Local de armazenamento.
- Como recriar infraestrutura (instâncias).
- Como restaurar backup via script.

### Disaster Recovery

Reconstrução total pós-falha.

**Estratégia exige:**

- Frequência (diário/hora).
- Local de armazenamento.
- Como recriar infraestrutura (instâncias).
- Como restaurar backup via script.

---

# ORGANIZAÇÃO DO TRABALHO

## Divisão de Responsabilidades

**Todos:** responsáveis pela documentação do projeto, organização e controle de versão no GitHub, integração entre as partes do sistema e definição do System Design.

### Pedro Antonio

- Desenvolvimento da interface do cliente
- Implementação da interface em Python/Django
- Construção das telas e fluxo de interação
- Integração da interface com a API
- Participação na definição da experiência do usuário

### Tauan Gomes

- Integração entre Front-end e Back-end
- Implementação e integração da API GraphQL
- Desenvolvimento das regras de comunicação do sistema
- Autenticação e autorização
- Implementação das estratégias de segurança

### Augusto Fagner

- Desenvolvimento do Back-end em Node.js + TypeScript
- Implementação das regras de negócio
- Estruturação da camada de acesso aos dados
- Integração com Prisma e banco de dados
- Organização da arquitetura do servidor

---

# CONTROLE DE VERSÃO

## Git & GitHub

Repositório utilizado para estruturar tecnologias base. Implementação em progresso contínuo.

https://github.com/pedrom0ta/ByteBistro

---

# ROTEIRO

## Entrega acadêmica

- Demonstração local com cardápio, carrinho, pedidos, acompanhamento e painel em Django e SQLite.
- System Design escrito, diagramas, infraestrutura AWS definida em Terraform e roteiro de apresentação.

## Evolução para produção

- Implementar o backend Node.js e TypeScript, disponibilizar a API Apollo/GraphQL e integrar o cliente Django.
- Migrar a persistência do domínio para Prisma e PostgreSQL e implementar mensageria com workers.
- Provisionar a infraestrutura AWS, validar a integração em homologação e publicar a aplicação.

[Roteiro de apresentação](docs/apresentacao/README.md)

---

# Síntese do Projeto

### Problema

Digitalização de fluxos em restaurantes.

### Solução

Plataforma centralizada Cliente-Servidor.

### Arquitetura

Monólito Modular escalável no futuro.

### Comunicação

A integração proposta usa HTTP e GraphQL entre Django e Node.js. O Prisma acessa o PostgreSQL.

### Segurança

Validação no backend; rede segmentada.

### Escala

De instância única para Load Balancer.

### Resiliência

Planejamento de Retry, Circuit Breaker e DLQ.

### Domínio

Sistemas Distribuídos aplicados à Gastronomia.

---
# CRONOGRAMA DE ENTREGA

## Etapas da entrega acadêmica

| Etapa | Atividade | Status |
| --- | --- | --- |
| **Etapa 1** | Definição do domínio, problema e proposta do ByteBistro | ✅ Concluída |
| **Etapa 2** | Definição da arquitetura e das tecnologias | ✅ Concluída |
| **Etapa 3** | Estruturação do repositório e organização inicial | ✅ Concluída |
| **Etapa 4** | Implementação da interface web e do painel em Django | ✅ Concluída |
| **Etapa 5** | Implementação das regras de carrinho e pedidos em Django | ✅ Concluída |
| **Etapa 6** | Implementação das rotas web e da consulta de status | ✅ Concluída |
| **Etapa 7** | Persistência local com ORM Django e SQLite | ✅ Concluída |
| **Etapa 8** | Integração da vitrine com o checkout e o painel | ✅ Concluída |
| **Etapa 9** | Autenticação, sessões e controle de acesso na demonstração | ✅ Concluída |
| **Etapa 10** | Validação da demonstração com a suíte de testes Django | ✅ Concluída |
| **Etapa 11** | Documentação do System Design, diagrama AWS e preparação do Terraform | ✅ Concluída |
| **Etapa 12** | Preparação do roteiro de apresentação da entrega acadêmica | ✅ Concluída |

---

# Obrigado!

## Perguntas?
