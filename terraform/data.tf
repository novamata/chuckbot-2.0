data "aws_caller_identity" "current" {}

data "archive_file" "daily_quote_sender_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/daily_quote_sender"
  output_path = "${path.module}/daily_quote_sender.zip"
}

data "archive_file" "quote_generator_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/quote_generator"
  output_path = "${path.module}/quote_generator.zip"
}