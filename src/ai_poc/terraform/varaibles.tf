variable "gcp_project_id" {
  type        = string
  description = "The GCP project ID to deploy resources into."
}

variable "gcp_region" {
  type        = string
  description = "The GCP region for the resources."
  default     = "us-east1"
}

variable "dataset_id" {
  type        = string
  description = "The ID for the BigQuery dataset."
  default     = "insurance_poc_dataset"
}

variable "metrics_table_id" {
  type        = string
  description = "The ID for the BigQuery table that will store financial metrics."
  default     = "financial_metrics"
}

variable "storage_bucket_name" {
  type        = string
  description = "The name of the Cloud Storage bucket for reports. Must be globally unique."
  default     = "commercial_insurance_summary_reports"
}

variable "data_store_id" {
  type        = string
  description = "A unique ID for the Vertex AI Search data store."
  default     = "insurance-filings-store"
}