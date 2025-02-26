output "quote_generator_lambda_name" {
  description = "Name of the Quote Generator Lambda function."
  value       = aws_lambda_function.quote_generator.function_name
}
