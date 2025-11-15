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

# Bucket 1: For staging raw 10-K/10-Q filings before ingestion into Vertex AI
resource "google_storage_bucket" "filings_bucket" {
  project       = var.gcp_project_id
  name          = "${var.gcp_project_id}-filings-bucket"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true
}

# Bucket 2: For storing the final AI-generated executive summaries
resource "google_storage_bucket" "report_bucket" {
  project       = var.gcp_project_id
  name          = "${var.gcp_project_id}-report-bucket"
  location      = var.gcp_region
  force_destroy = true

  uniform_bucket_level_access = true
}

# Create the Vertex AI Search Data Store
resource "google_discovery_engine_data_store" "filings_data_store" {
  project           = var.gcp_project_id
  location          = "global"
  data_store_id     = var.data_store_id
  display_name      = "Insurance Filings Data Store"
  solution_types    = ["SOLUTION_TYPE_SEARCH"]
  content_config    = "CONTENT_REQUIRED"
  industry_vertical = "GENERIC"

  depends_on = [google_project_service.discoveryengine]
}