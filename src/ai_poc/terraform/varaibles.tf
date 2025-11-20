variable "gcp_project_id" {
  type        = string
  description = "The GCP project ID to deploy resources into."
}

variable "gcp_region" {
  type        = string
  description = "The GCP region for the resources."
  default     = "us-east1"
}

variable "data_store_id" {
  type        = string
  description = "A unique ID for the Vertex AI Search data store."
  default     = "insurance-filings-full"
}

variable "data_store_id_test" {
  type        = string
  description = "A unique ID for the Vertex AI Search data store."
  default     = "insurance-filings-test"
}