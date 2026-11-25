variable "region" {

  type = string

  validation {

    condition = can(regex("^[a-z]{2}(-[a-z0-9]+)+-[0-9]+$", var.region))

    error_message = "Informe um identificador válido de região AWS."

  }

}



variable "name" {

  type = string

  default = "bytebistro"

  validation {

    condition = can(regex("^[a-z][a-z0-9-]{1,18}[a-z0-9]$", var.name))

    error_message = "Use 3 a 20 caracteres minúsculos, números e hífens."

  }

}



variable "domain" {
  description = "Mandatory public custom hostname served by CloudFront and Route 53."
  type        = string
  nullable    = false

  validation {
    condition     = length(var.domain) <= 56 && can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z][a-z0-9-]*$", var.domain))
    error_message = "Use a lowercase DNS hostname of up to 56 characters."
  }
}

variable "hosted_zone_id" {
  description = "Mandatory Route 53 public hosted zone ID for the custom domain and ACM validation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^Z[A-Z0-9]+$", var.hosted_zone_id))
    error_message = "Provide a valid Route 53 public hosted zone ID (for example, Z1234567890ABC)."
  }
}

variable "waf_enforce" {
  description = "Enforce blocking for AWSManagedRulesCommonRuleSet on the CloudFront Web ACL (false uses count mode)."
  type        = bool
  default     = true
  nullable    = false
}

variable "runtime" {
  description = "Digests sha256 das imagens Docker nos repositórios ECR desta infraestrutura para ativação das frotas web, api e worker."
  type = object({
    web_digest    = string
    api_digest    = string
    worker_digest = string
  })
  default = null

  validation {
    condition = var.runtime == null ? true : alltrue([
      for digest in [var.runtime.web_digest, var.runtime.api_digest, var.runtime.worker_digest] :
      can(regex("^sha256:[a-f0-9]{64}$", digest))
    ])
    error_message = "Forneça digests sha256 completos para as três imagens."
  }
}



variable "instance_type" {

  type = string

  default = "t3.small"

}



variable "db_instance_class" {

  type = string

  default = "db.t4g.medium"

}



variable "db_backup_retention_period" {
  type    = number
  default = 1
  validation {
    condition     = var.db_backup_retention_period >= 1 && var.db_backup_retention_period <= 35 && floor(var.db_backup_retention_period) == var.db_backup_retention_period
    error_message = "Use a whole number from 1 to 35 for RDS backup retention."
  }
}

variable "ops_email" {

  description = "Email opcional para alarmes; o destinatário confirma a assinatura."

  type = string

  default = null

}

variable "notification_email" {
  description = "Email opcional para notificações de pedidos via SNS; o destinatário confirma a assinatura."
  type        = string
  default     = null

  validation {
    condition     = var.notification_email == null ? true : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.notification_email))
    error_message = "Informe um endereço de e-mail válido para notificações."
  }
}

