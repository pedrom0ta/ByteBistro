terraform {
  backend "s3" {}

  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "ByteBistro", Environment = var.name }
  }
}

provider "aws" {
  alias  = "edge"
  region = "us-east-1"
  default_tags {
    tags = { Project = "ByteBistro", Environment = var.name }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}
