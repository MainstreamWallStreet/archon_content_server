terraform {
  backend "gcs" {
    bucket = "banshee-tf-state-202407"
    prefix = "terraform/state"
  }
}
