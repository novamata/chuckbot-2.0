variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
}

variable "discord_bot_token" {
  description = "Discord Bot Token"
  type        = string
  sensitive   = true
}

variable "discord_client_id" {
  description = "Discord Application Client ID"
  type        = string
}

variable "discord_public_key" {
  description = "Discord Application Public Key"
  type        = string
}

variable "discord_channel_id" {
  description = "Discord Channel ID to send daily quotes"
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