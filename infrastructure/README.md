# Infrastructure

## Infraestrutura atual

```
AWS
└── EC2
    └── Aplicação
```

Atualmente, o ByteBistro está planejado para ser hospedado em uma única instância **AWS EC2**, responsável por executar a aplicação.

## Evolução planejada

As propostas abaixo representam conceitos de evolução arquitetural discutidos para a disciplina de Sistemas Distribuídos, e **não fazem parte da infraestrutura atualmente implementada**:

- **Load Balancer** — distribuição de requisições entre múltiplas instâncias
- **Auto Scaling** — ajuste automático da quantidade de instâncias conforme a demanda
- **Múltiplas EC2** — execução do backend em paralelo em mais de uma instância
- **Banco compartilhado** — substituição do banco local por um banco compartilhado entre instâncias (ver [`database/README.md`](../database/README.md))
- **Segurança de rede** — uso de Security Groups e segmentação de rede
- **DNS** — uso de domínio próprio com resolução de nomes para acesso ao sistema

Mais detalhes conceituais em [`docs/arquitetura/arquitetura-futura.md`](../docs/arquitetura/arquitetura-futura.md).

## Status

🟡 Em fase de planejamento. Nenhum script de infraestrutura (Terraform, CloudFormation ou similar) foi criado neste momento.
