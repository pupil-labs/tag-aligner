import shutil

import requests

class CloudAPI:
	def __init__(self, key, base_url="https://api.cloud.pupil-labs.com/v2"):
		self.key = key
		self.base_url = base_url

	def api_get(self, path):
		url = f"{self.base_url}{path}"

		def parse_response(response):
			cloud_response = response.json()

			if cloud_response["status"] == "success":
				return cloud_response["result"]

			else:
				error = cloud_response["message"]
				raise Exception(error)

		return parse_response(requests.get(url, headers={"api-key": self.key}))

	def download_url(self, path, save_path, chunk_size=128):
		url = f"{self.base_url}{path}"

		r = requests.get(url, stream=True, headers={"api-key": self.key})
		with open(save_path, "wb") as fd:
			for chunk in r.iter_content(chunk_size=chunk_size):
				fd.write(chunk)

	def get_recording_details(self, workspace_id, project_id, recording_id):
		return self.api_get(f"/workspaces/{workspace_id}/recordings/{recording_id}")

	def get_enrichment_list(self, workspace_id, project_id):
		return self.api_get(f"/workspaces/{workspace_id}/projects/{project_id}/enrichments/")

	def get_enrichment(self, workspace_id, project_id, enrichment_id):
		return self.api_get(f"/workspaces/{workspace_id}/projects/{project_id}/enrichments/{enrichment_id}")

	def get_camera_poses(self, workspace_id, project_id, markerless_id, recording_id):
		return self.api_get(
			f"/workspaces/{workspace_id}/markerless/{markerless_id}/recordings/{recording_id}/camera_pose.json",
		)

	def download_recording(self, workspace_id, recording_id, download_path):
		download_path.mkdir(parents=True, exist_ok=True)

		self.download_url(
			f"/workspaces/{workspace_id}/recordings:raw-data-export?ids={recording_id}",
			download_path / f"{recording_id}.zip"
		)

		shutil.unpack_archive(
			download_path/f"{recording_id}.zip",
			download_path
		)
		(download_path / f"{recording_id}.zip").unlink()
		for file_source in (download_path).glob("*/*"):
			file_destination = file_source.parents[1] / file_source.name
			shutil.move(file_source, file_destination)

		for potential_folder in (download_path).glob("*"):
			if potential_folder.is_dir():
				potential_folder.rmdir()
