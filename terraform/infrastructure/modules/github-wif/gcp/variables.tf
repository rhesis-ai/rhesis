variable "project_id" {
  description = "Project that owns the pool (the admin project)."
  type        = string
}

variable "repository" {
  description = "The only GitHub repository whose tokens the provider accepts, as owner/name."
  type        = string
  default     = "rhesis-ai/rhesis"
}
