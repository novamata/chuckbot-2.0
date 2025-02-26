# ===========================#
# Terraform Configuration    #
# ===========================#
provider "aws" {
  region = var.aws_region
}

# ===========================#
# IAM                        #
# ===========================#

resource "aws_iam_role" "lambda_execution_role" {
  name = "discord_bot_lambda_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "discord_bot_lambda_policy"
  description = "Policy for Discord Bot Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "dynamodb:PutItem",
          "dynamodb:Scan",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.quotes_table.arn
      },
      {
        Effect   = "Allow"
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:discord_bot_secrets-*"
      }
    ]
  })
}

resource "aws_iam_policy" "secrets_manager_policy" {
  name        = "discord_bot_secrets_manager_policy"
  description = "Policy to allow Lambda to access Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:discord_bot_secrets-*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach_policy" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_attach_secrets_policy" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.secrets_manager_policy.arn
}

data "aws_caller_identity" "current" {}

# ===========================#
# Lambda                     #
# ===========================#

resource "aws_lambda_function" "interaction_handler" {
  filename         = data.archive_file.interaction_handler_zip.output_path
  function_name    = "DiscordInteractionHandler"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.10"
  source_code_hash = filebase64sha256(data.archive_file.interaction_handler_zip.output_path)

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.quotes_table.name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_attach_policy,
    aws_dynamodb_table.quotes_table
  ]
}

resource "aws_lambda_function" "daily_quote_sender" {
  filename         = data.archive_file.daily_quote_sender_zip.output_path
  function_name    = "DailyQuoteSender"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.10"
  source_code_hash = filebase64sha256(data.archive_file.daily_quote_sender_zip.output_path)

  environment {
    variables = {
      DYNAMODB_TABLE     = aws_dynamodb_table.quotes_table.name
      DISCORD_WEBHOOK_URL = var.discord_webhook_url
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_attach_policy,
    aws_dynamodb_table.quotes_table
  ]
}

resource "aws_lambda_layer_version" "openai_layer" {
  filename   = "${path.module}/../lambda_layer/openai_layer.zip"  
  layer_name = "discord_bot_dependencies"
  compatible_runtimes = ["python3.10"]
}

resource "aws_lambda_function" "quote_generator" {
  filename         = data.archive_file.quote_generator_zip.output_path
  function_name    = "QuoteGenerator"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "quote_generator.lambda_handler"
  runtime          = "python3.10"
  source_code_hash = filebase64sha256(data.archive_file.quote_generator_zip.output_path)

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.quotes_table.name
      REGION     = var.aws_region
    }
  }
  timeout = 15
  
  layers = [
    aws_lambda_layer_version.openai_layer.arn
  ]

  depends_on = [
    aws_iam_role_policy_attachment.lambda_attach_policy,
    aws_iam_role_policy_attachment.lambda_attach_secrets_policy,
    aws_dynamodb_table.quotes_table
  ]
}

# ===========================#
# Secrets Manager            #
# ===========================#

resource "aws_secretsmanager_secret" "discord_bot_secrets" {
  name        = "discord_bot_secrets"
  description = "Secrets for the Discord bot including the OpenAI API key"
}

resource "aws_secretsmanager_secret_version" "discord_bot_secrets_version" {
  secret_id     = aws_secretsmanager_secret.discord_bot_secrets.id
  secret_string = jsonencode({
    OPENAI_API_KEY = var.openai_api_key
  })
}


# ===========================#
# DynamoDB                   #
# ===========================#

resource "aws_dynamodb_table" "quotes_table" {
  name         = "ChuckNorrisQuotes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "QuoteID"

  attribute {
    name = "QuoteID"
    type = "S"
  }

  tags = {
    Application = "chuckbot-2.0"
  }
}

# ===========================#
# API Gateway                #
# ===========================#

resource "aws_api_gateway_rest_api" "discord_api" {
  name        = "DiscordInteractionAPI"
  description = "API Gateway for Discord Bot Interactions"
}

resource "aws_api_gateway_resource" "discord_interactions" {
  rest_api_id = aws_api_gateway_rest_api.discord_api.id
  parent_id   = aws_api_gateway_rest_api.discord_api.root_resource_id
  path_part   = "interactions"
}

resource "aws_api_gateway_method" "post_interactions" {
  rest_api_id   = aws_api_gateway_rest_api.discord_api.id
  resource_id   = aws_api_gateway_resource.discord_interactions.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.discord_api.id
  resource_id = aws_api_gateway_resource.discord_interactions.id
  http_method = aws_api_gateway_method.post_interactions.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.interaction_handler.invoke_arn
}

resource "aws_api_gateway_deployment" "discord_api_deployment" {
  depends_on = [
    aws_api_gateway_integration.lambda_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.discord_api.id
}

resource "aws_lambda_permission" "api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.interaction_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.discord_api.execution_arn}/*/*"
}

output "api_gateway_url" {
  description = "API Gateway endpoint URL for Discord interactions"
  value       = "${aws_api_gateway_deployment.discord_api_deployment.invoke_url}/interactions"
}

# ===========================#
# Eventbridge                #
# ===========================#

resource "aws_cloudwatch_event_rule" "daily_quote_schedule" {
  name                = "DailyQuoteGeneration"
  description         = "Triggers DailyQuoteSender Lambda every day at 9 AM UTC"
  schedule_expression = "cron(0 9 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_quote_target" {
  rule      = aws_cloudwatch_event_rule.daily_quote_schedule.name
  target_id = "DailyQuoteSender"
  arn       = aws_lambda_function.daily_quote_sender.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.daily_quote_sender.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_quote_schedule.arn
}

resource "aws_cloudwatch_event_rule" "quote_generator_schedule" {
  name                = "QuoteGeneratorSchedule"
  description         = "Triggers the quote generator Lambda on a schedule"
  schedule_expression = "cron(0/1 * * * ? *)"  # NEED TO ADJUST
}

resource "aws_cloudwatch_event_target" "quote_generator_target" {
  rule      = aws_cloudwatch_event_rule.quote_generator_schedule.name
  target_id = "QuoteGenerator"
  arn       = aws_lambda_function.quote_generator.arn
}

resource "aws_lambda_permission" "allow_eventbridge_quote_generator" {
  statement_id  = "AllowExecutionFromEventBridgeQuoteGenerator"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.quote_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.quote_generator_schedule.arn
}
