locals {
  zones         = { for i, az in slice(data.aws_availability_zones.available.names, 0, 2) : az => i }
  roles         = toset(["web", "api", "worker"])
  fleets        = toset(["web", "worker"])
  custom_domain = var.domain != null
  origin_domain = local.custom_domain ? "origin.${var.domain}" : aws_lb.web.dns_name
  public_domain = local.custom_domain ? var.domain : aws_cloudfront_distribution.app.domain_name
  origin_port   = local.custom_domain ? 443 : 80
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "public" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, each.value)
}

resource "aws_subnet" "private" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, each.value + 10)
}

resource "aws_subnet" "data" {
  for_each          = local.zones
  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, each.value + 20)
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  for_each       = local.zones
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  for_each = local.zones
  domain   = "vpc"
}

resource "aws_nat_gateway" "main" {
  for_each      = local.zones
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_route_table_association.public]
}

resource "aws_route_table" "private" {
  for_each = local.zones
  vpc_id   = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[each.key].id
  }
}

resource "aws_route_table_association" "private" {
  for_each       = local.zones
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table_association" "data" {
  for_each       = local.zones
  subnet_id      = aws_subnet.data[each.key].id
  route_table_id = aws_route_table.data.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id          = aws_vpc.main.id
  service_name    = "com.amazonaws.${var.region}.s3"
  route_table_ids = [for table in aws_route_table.private : table.id]
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "main" {
  for_each = toset(["alb", "web", "worker", "db"])
  name     = "${var.name}-${each.key}"
  vpc_id   = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "edge" {
  security_group_id = aws_security_group.main["alb"].id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = local.origin_port
  to_port           = local.origin_port
}

resource "aws_vpc_security_group_ingress_rule" "web" {
  security_group_id            = aws_security_group.main["web"].id
  referenced_security_group_id = aws_security_group.main["alb"].id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "alb" {
  security_group_id            = aws_security_group.main["alb"].id
  referenced_security_group_id = aws_security_group.main["web"].id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "database" {
  for_each                     = local.fleets
  security_group_id            = aws_security_group.main["db"].id
  referenced_security_group_id = aws_security_group.main[each.key].id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "database" {
  for_each                     = local.fleets
  security_group_id            = aws_security_group.main[each.key].id
  referenced_security_group_id = aws_security_group.main["db"].id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "https" {
  for_each          = local.fleets
  security_group_id = aws_security_group.main[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
