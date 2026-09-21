# Arquitetura Futura

> ⚠️ **Aviso importante:**
> Os componentes descritos nesta seção representam propostas de evolução arquitetural e não necessariamente funcionalidades implementadas na versão atual do ByteBistro. Este documento tem caráter conceitual e serve como base de discussão para a disciplina de Sistemas Distribuídos.

## Visão geral da evolução proposta

```
        DNS
         │
         ▼
  Load Balancer
         │
         ▼
 ┌───────┴───────┐
 │               │
EC2 (Backend)  EC2 (Backend)
 │               │
 └───────┬───────┘
         ▼
Banco compartilhado (PostgreSQL)
```

## Conceitos discutidos para evolução

### DNS e roteamento
Uso de um domínio próprio, com registros DNS apontando para o(s) ponto(s) de entrada do sistema, permitindo resolução de nomes amigável em vez do acesso direto por IP.

### Load Balancer
Distribuição das requisições entre múltiplas instâncias do backend, evitando sobrecarga em um único servidor e aumentando a disponibilidade do sistema.

### Múltiplas instâncias EC2
Em vez de uma única instância executando o backend, propõe-se a execução de várias instâncias em paralelo, permitindo escalabilidade horizontal.

### Auto Scaling
Ajuste automático da quantidade de instâncias em execução, de acordo com a demanda de uso do sistema.

### Banco de dados compartilhado (PostgreSQL)
Substituição do SQLite (banco local/arquivo) por um banco de dados compartilhado, como o PostgreSQL, permitindo que múltiplas instâncias do backend acessem uma única fonte de dados consistente.

### Retry
Estratégia de repetição automática de operações que falham temporariamente, aumentando a resiliência do sistema a falhas transitórias.

### Circuit Breaker
Padrão utilizado para evitar que falhas em um componente se propaguem para o restante do sistema, interrompendo temporariamente chamadas a um serviço que esteja apresentando falhas recorrentes.

### Filas e DLQ (Dead Letter Queue)
Uso de filas para processamento assíncrono de tarefas, com uma DLQ destinada a armazenar mensagens que não puderam ser processadas com sucesso, para posterior análise.

### Backup
Rotinas de cópia de segurança dos dados, reduzindo o risco de perda de informação.

### Disaster Recovery
Conjunto de estratégias e planos para restaurar o funcionamento do sistema em caso de falhas graves ou desastres.

### Evolução para serviços mais distribuídos
Discussão sobre uma possível divisão futura do monólito modular atual em serviços menores e mais independentes, caso a complexidade e a escala do projeto justifiquem essa mudança.

---

Para a arquitetura atualmente implementada, consulte [`arquitetura-atual.md`](arquitetura-atual.md).
