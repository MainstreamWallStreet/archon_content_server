terraform {
  backend "gcs" {
    bucket = "zergling-tf-state-202407"
    prefix = "terraform/state"
  }
}
