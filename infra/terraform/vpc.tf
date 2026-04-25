# VPC and Networking Infrastructure for GCP

# VPC Network
resource "google_compute_network" "main" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.gcp_project_id

  depends_on = [google_project_service.required_apis]
}

# Subnet
resource "google_compute_subnetwork" "main" {
  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.main.id
  project       = var.gcp_project_id

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Cloud Router for NAT
resource "google_compute_router" "main" {
  name    = "${local.name_prefix}-router"
  region  = var.gcp_region
  network = google_compute_network.main.id
  project = var.gcp_project_id

  bgp {
    asn = 64514
  }
}

# Cloud NAT for outbound internet access
resource "google_compute_router_nat" "main" {
  name                               = "${local.name_prefix}-nat"
  router                             = google_compute_router.main.name
  region                             = var.gcp_region
  project                            = var.gcp_project_id
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Serverless VPC Access Connector for Cloud Run
resource "google_vpc_access_connector" "main" {
  name          = "${local.name_prefix}-vpc-connector"
  region        = var.gcp_region
  project       = var.gcp_project_id
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"
  
  min_instances = 2
  max_instances = 10

  depends_on = [
    google_project_service.required_apis,
    google_compute_network.main
  ]
}

# Private Service Connection for Cloud SQL
resource "google_compute_global_address" "private_ip_address" {
  name          = "${local.name_prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
  project       = var.gcp_project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]

  depends_on = [google_project_service.required_apis]
}

# Firewall Rules
resource "google_compute_firewall" "allow_internal" {
  name    = "${local.name_prefix}-allow-internal"
  network = google_compute_network.main.name
  project = var.gcp_project_id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.vpc_cidr]
  priority      = 1000
}

resource "google_compute_firewall" "allow_health_check" {
  name    = "${local.name_prefix}-allow-health-check"
  network = google_compute_network.main.name
  project = var.gcp_project_id

  allow {
    protocol = "tcp"
    ports    = [var.container_port]
  }

  source_ranges = [
    "35.191.0.0/16",  # Google Cloud health check ranges
    "130.211.0.0/22"
  ]
  
  target_tags = ["${local.name_prefix}-app"]
  priority    = 1000
}

resource "google_compute_firewall" "allow_iap" {
  name    = "${local.name_prefix}-allow-iap"
  network = google_compute_network.main.name
  project = var.gcp_project_id

  allow {
    protocol = "tcp"
    ports    = ["22", "3389"]
  }

  source_ranges = ["35.235.240.0/20"]  # IAP forwarder range
  priority      = 1000
}