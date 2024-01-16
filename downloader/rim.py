import argparse
import pickle
from pathlib import Path

from .cloud_api import CloudAPI

def safe_filename(name):
	return "".join(c for c in name if c.isalpha() or c.isdigit() or c in ' -_').rstrip()


parser = argparse.ArgumentParser()
parser.add_argument("api_key")
parser.add_argument("workspace_id")
parser.add_argument("project_id")
parser.add_argument("enrichment_id")
parser.add_argument("recording_id", nargs="+")

parser.add_argument("--api_url", default="https://api.cloud.pupil-labs.com/v2")
parser.add_argument("--destination", type=Path, default=Path("recordings"))

args = parser.parse_args()

api = CloudAPI(args.api_key, args.api_url)


enrichment = api.get_enrichment(args.workspace_id, args.project_id, args.enrichment_id)
for rec_id in args.recording_id:
	recording = api.get_recording_details(args.workspace_id, args.project_id, rec_id)
	recording_name = safe_filename(recording["name"])

	download_path = args.destination / recording_name

	print(f"Downloading recording to {download_path}...")
	api.download_recording(args.workspace_id, rec_id, download_path)

	pose_file = download_path / "poses.p"

	print(f"Downloading poses to {pose_file}...")
	poses = api.get_camera_poses(
		args.workspace_id,
		args.project_id,
		enrichment['args']['markerless_id'],
		rec_id,
	)
	with (download_path / "poses.p").open("bw") as output_file:
		pickle.dump(poses, output_file)
