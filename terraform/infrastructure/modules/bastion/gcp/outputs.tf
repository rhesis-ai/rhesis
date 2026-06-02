output "bastion_name" {
  description = "Name of the bastion VM"
  value       = google_compute_instance.bastion.name
}

output "bastion_zone" {
  description = "Zone of the bastion VM"
  value       = google_compute_instance.bastion.zone
}

output "bastion_internal_ip" {
  description = "Internal IP of the bastion VM (in nodes subnet)"
  value       = google_compute_instance.bastion.network_interface[0].network_ip
}
