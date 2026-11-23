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
  description = "Optional custom hostname. Null uses the CloudFront distribution hostname."
  type        = string
  default     = null
  validation {
    condition     = var.domain == null ? true : length(var.domain) <= 56 && can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z][a-z0-9-]*$", var.domain))
    error_message = "Use a lowercase DNS hostname of up to 56 characters."
  }
}

variable "hosted_zone_id" {
  description = "Route 53 public zone ID when using a custom domain."
  type        = string
  default     = null

  validation {
    condition     = var.domain == null ? var.hosted_zone_id == null : can(regex("^Z[A-Z0-9]+$", var.hosted_zone_id))
    error_message = "Set both domain and hosted_zone_id, or leave both unset."
  }
}



variable "runtime" {

  description = "AMI Linux x86_64 com Docker, AWS CLI v2, Python 3 e SSM Agent. Imagens referenciam digests dos ECRs desta infraestrutura."

  type = object({

    ami_id = string

    web_digest = string

    api_digest = string

    worker_digest = string

    runtime_secret_arns = object({

      web = string

      api = string

      worker = string

    })

  })

  default = null

  validation {

    condition = var.runtime == null ? true : alltrue([

      for arn in values(var.runtime.runtime_secret_arns) :

      can(regex("^arn:[a-z0-9-]+:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+$", arn))

    ])

    error_message = "Informe ARNs completos dos segredos de execução."

  }

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

