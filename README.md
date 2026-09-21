# ByteBistro

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
*(Python/Tkinter)*

↓ HTTP / GraphQL ↓

**Node.js + TypeScript**

↓  

**Apollo Server + Resolvers**

↓

**Prisma ORM**

↓

**Banco de Dados**

---

## Diagrama Conceitual

```text
┌─────────────────────┐
│       CLIENTE       │
│    Python/Tkinter   │
└──────────┬──────────┘
           │
           │ HTTP / GraphQL
           ▼
┌─────────────────────┐
│      BACKEND        │
│ Node.js + TypeScript│
│                     │
│ Apollo Server       │
│ Resolvers           │
└──────────┬──────────┘
           │
           │ Prisma ORM
           ▼
┌─────────────────────┐
│     BANCO DE DADOS  │
│                     │
│     PostgreSQL      │
└─────────────────────┘
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

# HOSPEDAGEM

## Infraestrutura

### AWS EC2

- **AWS:** Provedor Cloud.
- **EC2:** Máquina virtual alocada.
- **Conteúdo:** Aplicação Node.js + Banco PostgreSQL.

**Servidor EC2**

Backend Node.js

PostgreSQL

---

# ARMAZENAMENTO

## Banco de Dados e Persistência

### PROPOSTA

**PostgreSQL**

Banco de dados relacional em rede.

**Solução:** Permite que múltiplas instâncias EC2 acessem a mesma fonte da verdade.

---

# EVOLUÇÃO DE INFRAESTRUTURA

## Balanceamento de Carga

### PROPOSTA ARQUITETURA

**Usuários**

↓

**Load Balancer (Distribuidor)**

↓

**EC2 1 | EC2 2 | EC2 3**

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

# REDE

## Firewall e Segmentação

### INTERNET ABERTA

↓

### Borda / Load Balancer

Apenas HTTP/HTTPS (Portas 80/443)

↓

### API / Backend (AWS Security Group)

Bloqueia conexões diretas da internet. Libera SSH restrito.

↓

### Banco de Dados Privado

Sem acesso externo. Só responde ao Backend.

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

Capacidade do sistema de suportar aumento de usuários sem degradação.

### Vertical (Scale Up)

Aumentar RAM/CPU da mesma máquina.

### Horizontal (Scale Out)

Adicionar novas máquinas lado a lado.

---

# EVOLUÇÃO

## Gerenciamento de Tráfego Automático

### PROPOSTA DE ARQUITETURA

**Load Balancer**

Distribui requisições uniformemente entre instâncias, evitando sobrecarga em um único nó.

### Auto Scaling

**Pico de acesso?** Cria novas EC2.

**Baixo acesso?** Desliga EC2 para economizar.

---

# ANÁLISE CRÍTICA

## A barreira da Escalabilidade

### PROPOSTA

**LB + EC2s + PostgreSQL**

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
- Como recriar infraestrutura (EC2s).
- Como restaurar backup via script.

### Disaster Recovery

Reconstrução total pós-falha.

**Estratégia exige:**

- Frequência (diário/hora).
- Local de armazenamento.
- Como recriar infraestrutura (EC2s).
- Como restaurar backup via script.

---

# NOMES E ENDEREÇOS

## DNS: O mapa da internet

DNS traduz nomes fáceis em endereços IP. Ele não hospeda o site, apenas direciona o tráfego.

**api.bytebistro.com**

Domínio/Subdomínio → Resolução

**54.232.10.15**

Endereço IP AWS

---

# FLUXO DE REDE

## O Caminho da Requisição

> * Load Balancer e cluster EC2 marcam proposta futura.

**Usuário → DNS → Load Balancer* → AWS EC2 → Node.js → Banco**

---

# ORGANIZAÇÃO DO TRABALHO

## Divisão de Responsabilidades

**Todos:** responsáveis pela documentação do projeto, organização e controle de versão no GitHub, integração entre as partes do sistema e definição do System Design.

### Pedro Antonio

- Desenvolvimento da interface do cliente
- Implementação da interface em Python/Tkinter
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

# ROADMAP

## Realidade vs. Proposta de Evolução

### Implementado

- Repositório estruturado no Git
- Organização inicial do projeto
- Definição da arquitetura
- Definição das tecnologias
- Monólito Modular

### Evolução Proposta

- Python + Tkinter
- Node.js + Apollo + GraphQL
- Prisma + Banco de Dados
- Integração Cliente ↔ Backend
- Segurança e autenticação
- AWS / EC2
- Load Balancer
- Auto Scaling
- PostgreSQL
- Filas / DLQ
- Resiliência
- Disaster Recovery
- Microsserviços
---

# Síntese do Projeto

### Problema

Digitalização de fluxos em restaurantes.

### Solução

Plataforma centralizada Cliente-Servidor.

### Arquitetura

Monólito Modular escalável no futuro.

### Comunicação

HTTP e GraphQL blindando o banco.

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

## Etapas do Projeto

| Etapa | Atividade | Status |
|---|---|---|
| **Etapa 1** | Definição do domínio, problema e proposta do ByteBistro | ✅ Concluído |
| **Etapa 2** | Definição da arquitetura e tecnologias | ✅ Concluído |
| **Etapa 3** | Estruturação do repositório e organização inicial do projeto | ✅ Concluído |
| **Etapa 4** | Desenvolvimento da interface do cliente com Python/Tkinter | 🔄 Em desenvolvimento |
| **Etapa 5** | Desenvolvimento do Backend com Node.js + TypeScript | 🔄 Em desenvolvimento |
| **Etapa 6** | Implementação da API GraphQL com Apollo Server e Resolvers | ⏳ Planejado |
| **Etapa 7** | Integração Prisma + PostgreSQL | ⏳ Planejado |
| **Etapa 8** | Integração Cliente ↔ Backend | ⏳ Planejado |
| **Etapa 9** | Implementação de autenticação, autorização e segurança | ⏳ Planejado |
| **Etapa 10** | Testes e validação do sistema | ⏳ Planejado |
| **Etapa 11** | Documentação e ajustes finais | ⏳ Planejado |
| **Etapa 12** | Entrega e apresentação do projeto | ⏳ Planejado |

### Legenda

- ✅ **Concluído**
- 🔄 **Em desenvolvimento**
- ⏳ **Planejado**

---

# Obrigado!

## Perguntas?
