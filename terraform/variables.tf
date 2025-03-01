variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
}

variable "openai_api_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
}

variable "discord_webhook_url" {
  description = "Discord Webhook URL for daily quotes"
  type        = string
}