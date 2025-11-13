terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Enable necessary APIs for the project
resource "google_project_service" "bigquery" {
  project = var.gcp_project_id
  service = "bigquery.googleapis.com"
}

resource "google_project_service" "storage" {
  project = var.gcp_project_id
  service = "storage.googleapis.com"
}

# Enable the Vertex AI Search API (Discovery Engine)
resource "google_project_service" "discoveryengine" {
  project = var.gcp_project_id
  service = "discoveryengine.googleapis.com"
}

# Create a BigQuery dataset to hold our tables
resource "google_bigquery_dataset" "dataset" {
  project    = var.gcp_project_id
  dataset_id = var.dataset_id
  location   = var.gcp_region

  depends_on = [google_project_service.bigquery]
}

# Create the BigQuery table for storing structured XBRL data
resource "google_bigquery_table" "financial_metrics_table" {
  project    = var.gcp_project_id
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  table_id   = var.metrics_table_id

  schema = jsonencode([
    {
      "name" : "CompanyTicker",
      "type" : "STRING",
      "mode" : "REQUIRED",
      "description" : "The stock ticker symbol for the company."
    },
    {
      "name" : "ReportDate",
      "type" : "DATE",
      "mode" : "REQUIRED",
      "description" : "The end date of the reporting period."
    },
    {
      "name" : "MetricName",
      "type" : "STRING",
      "mode" : "REQUIRED",
      "description" : "The name of the financial metric (e.g., 'Revenues', 'NetIncomeLoss')."
    },
    {
      "name" : "MetricValue",
      "type" : "NUMERIC",
      "mode" : "REQUIRED",
      "description" : "The value of the metric."
    },
    {
      "name" : "Unit",
      "type" : "STRING",
      "mode" : "NULLABLE",
      "description" : "The unit of the metric (e.g., 'USD', 'shares')."
    }
  ])
}

# Create a Cloud Storage bucket for storing generated reports
resource "google_storage_bucket" "report_bucket" {
  project      = var.gcp_project_id
  name         = var.storage_bucket_name
  location     = var.gcp_region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  depends_on = [google_project_service.storage]
}

# Create the Vertex AI Search Data Store for unstructured 10-K/10-Q text
resource "google_discovery_engine_data_store" "filings_data_store" {
  project           = var.gcp_project_id
  location          = "global" # Vertex AI Search data stores are often global
  data_store_id     = var.data_store_id
  display_name      = "Insurance Filings Data Store"
  solution_types    = ["SOLUTION_TYPE_SEARCH"]
  content_config    = "CONTENT_REQUIRED"
  industry_vertical = "GENERIC" # This line is now required

  depends_on = [google_project_service.discoveryengine]
}